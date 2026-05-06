from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.db.database import get_db
from app.dependencies import verifyActiveSession
from app.auth.auth import verifySession

router = APIRouter(prefix="/participation", tags=["Participation"])

# ── Niveles ──────────────────────────────────────────────────────
LEVELS = [
    (45, 'Referente solidario',   '#FF895E', 'Tu ayuda inspira a otros'),
    (35, 'Colaborador confiable', '#4A90E2', 'La comunidad confía en ti'),
    (20, 'Apoyo activo',          '#4FB6A6', 'Ayudar ya es parte de ti'),
    (10, 'Colaborador',           '#94E9AE', 'Tus acciones ayudan'),
    (5,  'Participante',          '#8EC5D1', 'Formas parte de la comunidad'),
]

# Puntos máximos por tipo de acción al día (anti-abuso)
DAILY_LIMITS = {
    'CREATE_POST':          15,
    'CREATE_COMMENT':       12,
    'CREATE_REPLY':         12,
    'REACTION':              5,
    'MODERATION_VOTE':       5,
    'HIGH_RATING_GIVEN':     4,
    'HIGH_RATING_RECEIVED': None,
}

POINTS = {
    'CREATE_POST':          5,
    'CREATE_COMMENT':       3,
    'CREATE_REPLY':         3,
    'REACTION':             1,
    'MODERATION_VOTE':      1,
    'HIGH_RATING_GIVEN':    2,
    'HIGH_RATING_RECEIVED': 5,
}


def get_badge(points: int) -> dict:
    for min_pts, label, color, mensaje in LEVELS:
        if points >= min_pts:
            return {'label': label, 'color': color, 'mensaje': mensaje, 'puntos': points}
    return {'label': None, 'color': None, 'mensaje': None, 'puntos': points}


def award_points(db: Session, user_id: int, action_type: str,
                 entity_type: str, entity_id: str) -> bool:
    """
    Awards participation points to a user for a given action.
    Returns True if points were awarded, False otherwise.
    """
    user = db.execute(
        text("SELECT status FROM usuarios WHERE id = :id"), {"id": user_id}
    ).fetchone()
    if not user or user.status in ('SUSPENDIDO', 'BANEADO'):
        return False

    pts = POINTS.get(action_type, 0)
    if pts == 0:
        return False

    # Check daily limit
    daily_limit = DAILY_LIMITS.get(action_type)
    if daily_limit is not None:
        today_pts = db.execute(text("""
            SELECT COALESCE(SUM(points), 0) FROM participation_log
            WHERE user_id = :uid AND action_type = :at AND DATE(created_at) = CURDATE()
        """), {"uid": user_id, "at": action_type}).scalar() or 0
        if today_pts >= daily_limit:
            return False

    # INSERT IGNORE prevents duplicate awards (UNIQUE KEY on user+action+entity)
    result = db.execute(text("""
        INSERT IGNORE INTO participation_log
            (user_id, action_type, entity_type, entity_id, points)
        VALUES (:uid, :at, :et, :eid, :pts)
    """), {
        "uid": user_id, "at": action_type,
        "et": entity_type, "eid": str(entity_id), "pts": pts,
    })

    if result.rowcount == 0:
        return False

    db.execute(text("""
        UPDATE usuarios SET puntos_participacion = puntos_participacion + :pts WHERE id = :uid
    """), {"pts": pts, "uid": user_id})

    return True


# ── Endpoints ────────────────────────────────────────────────────

@router.get("/me")
async def get_my_participation(
    db: Session = Depends(get_db),
    id_user: str = Depends(verifyActiveSession),
):
    row = db.execute(
        text("SELECT puntos_participacion, status FROM usuarios WHERE id = :id"),
        {"id": id_user}
    ).fetchone()
    if not row:
        return {"status": "success", "badge": get_badge(0)}

    pts = row.puntos_participacion if row.status not in ('BANEADO',) else 0
    return {"status": "success", "badge": get_badge(pts)}


@router.get("/user/{user_id}")
async def get_user_participation(
    user_id: int,
    db: Session = Depends(get_db),
    _: str = Depends(verifySession),
):
    row = db.execute(
        text("SELECT puntos_participacion, status FROM usuarios WHERE id = :id"),
        {"id": user_id}
    ).fetchone()
    if not row or row.status == 'BANEADO':
        return {"status": "success", "badge": get_badge(0)}

    return {"status": "success", "badge": get_badge(row.puntos_participacion)}


@router.get("/batch")
async def get_batch_participation(
    ids: str,  # comma-separated numeric user ids
    db: Session = Depends(get_db),
    _: str = Depends(verifySession),
):
    id_list = [int(i) for i in ids.split(',') if i.strip().isdigit()]
    if not id_list:
        return {"status": "success", "badges": {}}

    rows = db.execute(text("""
        SELECT id, puntos_participacion, status FROM usuarios
        WHERE id IN :ids
    """), {"ids": tuple(id_list)}).fetchall()

    badges = {}
    for row in rows:
        pts = 0 if row.status == 'BANEADO' else row.puntos_participacion
        badges[str(row.id)] = get_badge(pts)

    return {"status": "success", "badges": badges}


@router.get("/batch-by-correo")
async def get_batch_by_correo(
    correos: str,  # comma-separated emails
    db: Session = Depends(get_db),
    _: str = Depends(verifySession),
):
    correo_list = [c.strip() for c in correos.split(',') if c.strip()]
    if not correo_list:
        return {"status": "success", "badges": {}}

    rows = db.execute(text("""
        SELECT correo, puntos_participacion, status FROM usuarios
        WHERE correo IN :correos
    """), {"correos": tuple(correo_list)}).fetchall()

    badges = {}
    for row in rows:
        pts = 0 if row.status == 'BANEADO' else row.puntos_participacion
        badges[row.correo] = get_badge(pts)

    return {"status": "success", "badges": badges}
