from datetime import datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.auth.auth import verifySession
from app.db.database import get_db
from app.dependencies import recover_suspension

router = APIRouter(prefix="/moderation", tags=["Moderation"])
limiter = Limiter(key_func=get_remote_address)

REPORT_THRESHOLD = 15
VOTE_HOURS = 24
SUSPENSION_DAYS = {1: 30, 2: 60}  # strike → días de suspensión


# ── Modelos ──────────────────────────────────────────────────

class UserReportBody(BaseModel):
    reported_correo: str
    motivo: Literal['spam', 'acoso', 'inapropiado', 'informacionFalsa']

class ModerationVoteBody(BaseModel):
    case_id: int
    voto: Literal['permanecer', 'sancionar']

class ContentStatusBody(BaseModel):
    cids: list[str]


# ── Helpers internos ─────────────────────────────────────────

def _resolve_expired(db: Session) -> None:
    """Resuelve casos cuyo periodo de 24 h ya venció."""
    expired = db.execute(text("""
        SELECT mc.id, mc.target_id, mc.keep_count, mc.sanction_count,
               u.strikes_count
        FROM user_moderation_cases mc
        JOIN usuarios u ON u.id = mc.target_id
        WHERE mc.status = 'OPEN' AND mc.voting_deadline <= NOW()
    """)).fetchall()

    for case in expired:
        if case.sanction_count > case.keep_count:
            new_strikes = case.strikes_count + 1
            if new_strikes >= 3:
                db.execute(text("""
                    UPDATE usuarios SET status='BANEADO', strikes_count=:s, ban_until=NULL
                    WHERE id=:id
                """), {"s": new_strikes, "id": case.target_id})
                _eliminate_user_content(db, case.target_id)
            else:
                days = SUSPENSION_DAYS.get(new_strikes, 30)
                ban_until = datetime.now() + timedelta(days=days)
                db.execute(text("""
                    UPDATE usuarios SET status='SUSPENDIDO', strikes_count=:s, ban_until=:bu
                    WHERE id=:id
                """), {"s": new_strikes, "bu": ban_until, "id": case.target_id})
            db.execute(text("""
                UPDATE user_moderation_cases
                SET status='RESOLVED_SANCTION', resolved_at=NOW()
                WHERE id=:id
            """), {"id": case.id})
        else:
            # Empate o mayoría permanecer → vuelve a NORMAL
            db.execute(text("UPDATE usuarios SET status='NORMAL' WHERE id=:id"),
                       {"id": case.target_id})
            db.execute(text("""
                UPDATE user_moderation_cases
                SET status='RESOLVED_KEEP', resolved_at=NOW()
                WHERE id=:id
            """), {"id": case.id})

        # Limpiar reportes para evitar que el mismo grupo vuelva a entrar de inmediato
        db.execute(text("DELETE FROM user_reports WHERE reported_id=:id"),
                   {"id": case.target_id})

    if expired:
        db.commit()


def _eliminate_user_content(db: Session, user_id: str) -> None:
    """Marca el contenido visible del usuario baneado como eliminado."""
    pubs = db.execute(
        text("SELECT cid_content FROM publications WHERE id_autor=:id"),
        {"id": user_id}
    ).fetchall()

    for pub in pubs:
        db.execute(text("""
            INSERT INTO content_status (cid, tipo, status, deleted_reason, deleted_at)
            VALUES (:cid, 'publicacion', 'ELIMINADA', 'AUTOR_BANEADO', NOW())
            ON DUPLICATE KEY UPDATE
                status='ELIMINADA', deleted_reason='AUTOR_BANEADO', deleted_at=NOW()
        """), {"cid": pub.cid_content})

        # Comentarios dentro de esa publicación (aunque sean de otros)
        db.execute(text("""
            INSERT INTO content_status (cid, tipo, status, deleted_reason, deleted_at)
            SELECT cid_content, 'comentario', 'ELIMINADO', 'PUBLICACION_PADRE_ELIMINADA', NOW()
            FROM comments WHERE publication_cid=:cid
            ON DUPLICATE KEY UPDATE
                status='ELIMINADO', deleted_reason='PUBLICACION_PADRE_ELIMINADA', deleted_at=NOW()
        """), {"cid": pub.cid_content})

    # Comentarios del usuario baneado en publicaciones ajenas
    db.execute(text("""
        INSERT INTO content_status (cid, tipo, status, deleted_reason, deleted_at)
        SELECT cid_content, 'comentario', 'ELIMINADO', 'AUTOR_BANEADO', NOW()
        FROM comments WHERE id_autor=:id
        ON DUPLICATE KEY UPDATE
            status='ELIMINADO', deleted_reason='AUTOR_BANEADO', deleted_at=NOW()
    """), {"id": user_id})



# ── Endpoints ────────────────────────────────────────────────

@router.get("/me")
async def get_my_status(
    db: Session = Depends(get_db),
    id_user: str = Depends(verifySession)
):
    """Devuelve el estado actual del alumno autenticado."""
    recover_suspension(db, id_user)
    row = db.execute(text("""
        SELECT status, strikes_count, ban_until
        FROM usuarios WHERE id=:id
    """), {"id": id_user}).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    return {
        "status":        row.status,
        "strikes_count": row.strikes_count,
        "ban_until":     row.ban_until.isoformat() if row.ban_until else None,
    }


@router.post("/users/report")
@limiter.limit("10/minute")
async def report_user(
    request: Request,
    body: UserReportBody,
    db: Session = Depends(get_db),
    id_reporter: str = Depends(verifySession)
):
    """Reporta a otro alumno. Máximo un reporte por par de usuarios."""
    # Verificar que el reporter no esté suspendido/baneado
    reporter_row = db.execute(
        text("SELECT status FROM usuarios WHERE id=:id"), {"id": id_reporter}
    ).fetchone()
    if reporter_row and reporter_row.status in ('SUSPENDIDO', 'BANEADO'):
        raise HTTPException(status_code=403, detail="No puedes reportar mientras estás suspendido o baneado")

    # Buscar al reportado por correo
    reported_row = db.execute(
        text("SELECT id, status, nombre FROM usuarios WHERE correo=:c"),
        {"c": body.reported_correo}
    ).fetchone()
    if not reported_row:
        raise HTTPException(status_code=404, detail="El usuario reportado no existe en el sistema")
    if reported_row.id == id_reporter:
        raise HTTPException(status_code=400, detail="No puedes reportarte a ti mismo")

    reported_id = reported_row.id

    # Verificar duplicado
    dup = db.execute(text("""
        SELECT id FROM user_reports
        WHERE reporter_id=:r AND reported_id=:d
    """), {"r": id_reporter, "d": reported_id}).fetchone()
    if dup:
        raise HTTPException(status_code=409, detail="Ya reportaste a este usuario anteriormente")

    # Insertar reporte
    db.execute(text("""
        INSERT INTO user_reports (reporter_id, reported_id, motivo, created_at)
        VALUES (:r, :d, :m, NOW())
    """), {"r": id_reporter, "d": reported_id, "m": body.motivo})
    db.commit()

    # Contar reportes únicos totales
    total = db.execute(text("""
        SELECT COUNT(*) as c FROM user_reports WHERE reported_id=:id
    """), {"id": reported_id}).fetchone().c

    # Entrar a moderación si se alcanzó el umbral y no hay caso abierto
    en_revision = False
    if total >= REPORT_THRESHOLD and reported_row.status == 'NORMAL':
        open_case = db.execute(text("""
            SELECT id FROM user_moderation_cases
            WHERE target_id=:id AND status='OPEN'
        """), {"id": reported_id}).fetchone()

        if not open_case:
            deadline = datetime.now() + timedelta(hours=VOTE_HOURS)
            db.execute(text("""
                INSERT INTO user_moderation_cases (target_id, status, voting_deadline)
                VALUES (:id, 'OPEN', :dl)
            """), {"id": reported_id, "dl": deadline})
            db.execute(text("""
                UPDATE usuarios SET status='EN_REVISION' WHERE id=:id
            """), {"id": reported_id})
            db.commit()
            en_revision = True

    return {
        "status":       "success",
        "total_reports": total,
        "en_revision":  en_revision or reported_row.status == 'EN_REVISION',
    }


@router.get("/users")
async def get_moderation_users(
    db: Session = Depends(get_db),
    id_user: str = Depends(verifySession)
):
    """Lista los alumnos actualmente en revisión (casos OPEN)."""
    _resolve_expired(db)

    rows = db.execute(text("""
        SELECT
            u.id, u.nombre, u.correo, u.status, u.strikes_count, u.ban_until,
            mc.id            AS case_id,
            mc.voting_deadline,
            mc.keep_count,
            mc.sanction_count,
            (SELECT COUNT(*)  FROM user_reports WHERE reported_id=u.id)                         AS total_reports,
            (SELECT COUNT(*)  FROM user_reports WHERE reported_id=u.id AND motivo='spam')        AS r_spam,
            (SELECT COUNT(*)  FROM user_reports WHERE reported_id=u.id AND motivo='acoso')       AS r_acoso,
            (SELECT COUNT(*)  FROM user_reports WHERE reported_id=u.id AND motivo='inapropiado') AS r_inapropiado,
            (SELECT COUNT(*)  FROM user_reports WHERE reported_id=u.id AND motivo='informacionFalsa') AS r_falsa,
            (SELECT voto FROM user_moderation_votes
             WHERE case_id=mc.id AND voter_id=:uid LIMIT 1)                                      AS mi_voto
        FROM usuarios u
        JOIN user_moderation_cases mc ON mc.target_id=u.id AND mc.status='OPEN'
        ORDER BY mc.created_at DESC
    """), {"uid": id_user}).fetchall()

    return {
        "status": "success",
        "users": [{
            "id":              r.id,
            "nombre":          r.nombre,
            "correo":          r.correo,
            "status":          r.status,
            "strikes_count":   r.strikes_count,
            "ban_until":       r.ban_until.isoformat() if r.ban_until else None,
            "case_id":         r.case_id,
            "voting_deadline": r.voting_deadline.isoformat(),
            "keep_count":      r.keep_count,
            "sanction_count":  r.sanction_count,
            "total_reports":   r.total_reports,
            "motivos": {
                "spam":             r.r_spam,
                "acoso":            r.r_acoso,
                "inapropiado":      r.r_inapropiado,
                "informacionFalsa": r.r_falsa,
            },
            "mi_voto": r.mi_voto,
        } for r in rows]
    }


@router.post("/users/vote")
@limiter.limit("20/minute")
async def vote_user_moderation(
    request: Request,
    body: ModerationVoteBody,
    db: Session = Depends(get_db),
    id_voter: str = Depends(verifySession)
):
    """Vota en un caso de moderación de alumno."""
    # Verificar que el votante pueda votar
    voter = db.execute(
        text("SELECT status FROM usuarios WHERE id=:id"), {"id": id_voter}
    ).fetchone()
    if voter and voter.status in ('SUSPENDIDO', 'BANEADO'):
        raise HTTPException(status_code=403, detail="No puedes votar mientras estás suspendido o baneado")

    # Verificar caso activo y plazo vigente
    case = db.execute(text("""
        SELECT id, status, voting_deadline FROM user_moderation_cases WHERE id=:id
    """), {"id": body.case_id}).fetchone()
    if not case:
        raise HTTPException(status_code=404, detail="Caso de moderación no encontrado")
    if case.status != 'OPEN':
        raise HTTPException(status_code=400, detail="Este caso ya fue resuelto")
    if datetime.now() > case.voting_deadline:
        raise HTTPException(status_code=400, detail="El periodo de votación ha terminado")

    # Verificar voto duplicado
    dup = db.execute(text("""
        SELECT id FROM user_moderation_votes WHERE case_id=:c AND voter_id=:v
    """), {"c": body.case_id, "v": id_voter}).fetchone()
    if dup:
        raise HTTPException(status_code=409, detail="Ya votaste en este caso")

    # Registrar voto
    db.execute(text("""
        INSERT INTO user_moderation_votes (case_id, voter_id, voto, created_at)
        VALUES (:c, :v, :voto, NOW())
    """), {"c": body.case_id, "v": id_voter, "voto": body.voto})

    # Actualizar contador
    col = "keep_count" if body.voto == "permanecer" else "sanction_count"
    db.execute(text(f"UPDATE user_moderation_cases SET {col}={col}+1 WHERE id=:id"),
               {"id": body.case_id})
    db.commit()

    updated = db.execute(text("""
        SELECT keep_count, sanction_count FROM user_moderation_cases WHERE id=:id
    """), {"id": body.case_id}).fetchone()

    return {
        "status":         "success",
        "keep_count":     updated.keep_count,
        "sanction_count": updated.sanction_count,
    }


@router.post("/content/status")
async def check_content_status(
    body: ContentStatusBody,
    db: Session = Depends(get_db),
    id_user: str = Depends(verifySession)
):
    """Devuelve el estado de eliminación de un lote de CIDs."""
    if not body.cids:
        return {"status": "success", "eliminated": []}

    cids_tuple = tuple(body.cids) if len(body.cids) > 1 else (body.cids[0],)
    rows = db.execute(text("""
        SELECT cid FROM content_status WHERE cid IN :cids
    """), {"cids": cids_tuple}).fetchall()

    eliminated = {r.cid for r in rows}
    return {
        "status":     "success",
        "eliminated": list(eliminated),
    }
