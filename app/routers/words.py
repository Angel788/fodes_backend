from datetime import datetime, timedelta
from pydantic import BaseModel
from fastapi import APIRouter, Depends, Request, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.db.database import get_db
from app.dependencies import verifyActiveSession

WORD_VOTE_MINUTES  = 24   # TODO: cambiar a horas en producción (24h)
DAILY_GLOBAL_LIMIT = 10
DAILY_USER_LIMIT   = 2

router  = APIRouter(prefix="/words", tags=["Words"])
limiter = Limiter(key_func=get_remote_address)


class ProposeWordBody(BaseModel):
    word: str


class VoteWordBody(BaseModel):
    voto: str  # 'aprobar' | 'descartar'


def normalize_word(word: str) -> str:
    return word.strip().lower()


def resolve_expired_words(db: Session):
    expired = db.execute(text("""
        SELECT id, approve_vote_count, discard_vote_count
        FROM word_proposals
        WHERE status = 'POR_APROBAR' AND voting_deadline < NOW()
    """)).fetchall()

    for row in expired:
        if row.approve_vote_count > row.discard_vote_count:
            db.execute(text("""
                UPDATE word_proposals
                SET status = 'APROBADA', approved_at = NOW(), resolved_at = NOW()
                WHERE id = :id
            """), {"id": row.id})
        else:
            db.execute(text("""
                UPDATE word_proposals
                SET status = 'DESCARTADA', resolved_at = NOW()
                WHERE id = :id
            """), {"id": row.id})

    if expired:
        db.commit()


def check_banned_words(fields: list[str], db: Session) -> str | None:
    """Returns the original banned word if any field contains it, else None."""
    approved = db.execute(text("""
        SELECT normalized_word, word FROM word_proposals WHERE status = 'APROBADA'
    """)).fetchall()

    if not approved:
        return None

    for field in fields:
        if not field:
            continue
        normalized_field = normalize_word(field)
        for row in approved:
            if row.normalized_word in normalized_field:
                return row.word

    return None


@router.get("")
async def get_words(
    db: Session = Depends(get_db),
    id_user: str = Depends(verifyActiveSession),
):
    resolve_expired_words(db)

    approved = db.execute(text("""
        SELECT id, word, normalized_word, approved_at
        FROM word_proposals
        WHERE status = 'APROBADA'
        ORDER BY approved_at DESC
    """)).fetchall()

    pending = db.execute(text("""
        SELECT wp.id, wp.word, wp.normalized_word, wp.voting_deadline,
               wp.approve_vote_count, wp.discard_vote_count,
               wv.voto AS mi_voto
        FROM word_proposals wp
        LEFT JOIN word_votes wv ON wv.word_id = wp.id AND wv.voter_id = :uid
        WHERE wp.status = 'POR_APROBAR'
        ORDER BY wp.proposed_at DESC
    """), {"uid": id_user}).fetchall()

    global_today = db.execute(text("""
        SELECT COUNT(*) FROM word_proposals WHERE DATE(proposed_at) = CURDATE()
    """)).scalar() or 0

    user_today = db.execute(text("""
        SELECT COUNT(*) FROM word_proposals
        WHERE proposed_by = :uid AND DATE(proposed_at) = CURDATE()
    """), {"uid": id_user}).scalar() or 0

    return {
        "status": "success",
        "approved": [
            {
                "id": r.id,
                "word": r.word,
                "normalized_word": r.normalized_word,
                "approved_at": r.approved_at,
            }
            for r in approved
        ],
        "pending": [
            {
                "id": r.id,
                "word": r.word,
                "normalized_word": r.normalized_word,
                "voting_deadline": r.voting_deadline,
                "approve_vote_count": r.approve_vote_count,
                "discard_vote_count": r.discard_vote_count,
                "mi_voto": r.mi_voto,
            }
            for r in pending
        ],
        "daily_global_remaining": max(0, DAILY_GLOBAL_LIMIT - global_today),
        "daily_user_remaining": max(0, DAILY_USER_LIMIT - user_today),
    }


@router.post("/propose")
@limiter.limit("5/minute")
async def propose_word(
    request: Request,
    body: ProposeWordBody,
    db: Session = Depends(get_db),
    id_user: str = Depends(verifyActiveSession),
):
    user = db.execute(
        text("SELECT status FROM usuarios WHERE id = :id"), {"id": id_user}
    ).fetchone()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    if user.status in ("SUSPENDIDO", "BANEADO"):
        raise HTTPException(status_code=403, detail="No puedes proponer palabras con tu estado actual")

    if not body.word or not body.word.strip():
        raise HTTPException(status_code=400, detail="La palabra no puede estar vacía")

    normalized = normalize_word(body.word)
    if len(normalized) < 2:
        raise HTTPException(status_code=400, detail="La palabra es demasiado corta")

    existing = db.execute(text("""
        SELECT id, status FROM word_proposals
        WHERE normalized_word = :nw AND status IN ('POR_APROBAR', 'APROBADA')
    """), {"nw": normalized}).fetchone()

    if existing:
        msg = ("Esta palabra ya está aprobada en la bolsa"
               if existing.status == "APROBADA"
               else "Esta palabra ya está siendo votada")
        raise HTTPException(status_code=409, detail=msg)

    global_count = db.execute(text("""
        SELECT COUNT(*) FROM word_proposals WHERE DATE(proposed_at) = CURDATE()
    """)).scalar() or 0
    if global_count >= DAILY_GLOBAL_LIMIT:
        raise HTTPException(
            status_code=429,
            detail="Se alcanzó el límite global de 10 palabras nuevas por día"
        )

    user_count = db.execute(text("""
        SELECT COUNT(*) FROM word_proposals
        WHERE proposed_by = :uid AND DATE(proposed_at) = CURDATE()
    """), {"uid": id_user}).scalar() or 0
    if user_count >= DAILY_USER_LIMIT:
        raise HTTPException(
            status_code=429,
            detail="Ya propusiste 2 palabras hoy. Intenta mañana"
        )

    deadline = datetime.now() + timedelta(minutes=WORD_VOTE_MINUTES)
    db.execute(text("""
        INSERT INTO word_proposals (word, normalized_word, proposed_by, voting_deadline)
        VALUES (:word, :nw, :uid, :deadline)
    """), {
        "word": body.word.strip(),
        "nw": normalized,
        "uid": id_user,
        "deadline": deadline,
    })
    db.commit()

    return {"status": "success", "message": "Palabra propuesta correctamente"}


@router.post("/{word_id}/vote")
@limiter.limit("20/minute")
async def vote_word(
    request: Request,
    word_id: int,
    body: VoteWordBody,
    db: Session = Depends(get_db),
    id_user: str = Depends(verifyActiveSession),
):
    if body.voto not in ("aprobar", "descartar"):
        raise HTTPException(status_code=400, detail="Voto inválido. Usa 'aprobar' o 'descartar'")

    user = db.execute(
        text("SELECT status FROM usuarios WHERE id = :id"), {"id": id_user}
    ).fetchone()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    if user.status in ("SUSPENDIDO", "BANEADO"):
        raise HTTPException(status_code=403, detail="No puedes votar con tu estado actual")

    word = db.execute(text("""
        SELECT id, status, voting_deadline
        FROM word_proposals WHERE id = :wid
    """), {"wid": word_id}).fetchone()

    if not word:
        raise HTTPException(status_code=404, detail="Palabra no encontrada")
    if word.status != "POR_APROBAR":
        raise HTTPException(status_code=410, detail="Esta palabra ya fue resuelta")
    if datetime.now() > word.voting_deadline:
        raise HTTPException(status_code=410, detail="El plazo de votación ya venció")

    existing_vote = db.execute(text("""
        SELECT id FROM word_votes WHERE word_id = :wid AND voter_id = :uid
    """), {"wid": word_id, "uid": id_user}).fetchone()
    if existing_vote:
        raise HTTPException(status_code=409, detail="Ya votaste por esta palabra")

    db.execute(text("""
        INSERT INTO word_votes (word_id, voter_id, voto) VALUES (:wid, :uid, :voto)
    """), {"wid": word_id, "uid": id_user, "voto": body.voto})

    if body.voto == "aprobar":
        db.execute(text("""
            UPDATE word_proposals SET approve_vote_count = approve_vote_count + 1 WHERE id = :wid
        """), {"wid": word_id})
    else:
        db.execute(text("""
            UPDATE word_proposals SET discard_vote_count = discard_vote_count + 1 WHERE id = :wid
        """), {"wid": word_id})

    db.commit()

    updated = db.execute(text("""
        SELECT approve_vote_count, discard_vote_count FROM word_proposals WHERE id = :wid
    """), {"wid": word_id}).fetchone()

    return {
        "status": "success",
        "approve_vote_count": updated.approve_vote_count,
        "discard_vote_count": updated.discard_vote_count,
    }
