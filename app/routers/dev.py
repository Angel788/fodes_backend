import os
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.db.database import get_db
from app.auth.auth import genHashPassword, genTokenUser

router = APIRouter(prefix="/dev", tags=["Dev"])

DEV_SECRET = os.getenv("DEV_SECRET", "")

def _check_secret(x_dev_secret: str = Header(None)):
    if not DEV_SECRET or x_dev_secret != DEV_SECRET:
        raise HTTPException(status_code=403, detail="Forbidden")

_SEED_MARKER = "@seed.fodes"
_PASSWORD    = "Seed1234!"
_HASH        = genHashPassword(_PASSWORD)

SEED_USERS = [
    {"nombre": "Seed Objetivo",  "correo": f"objetivo{_SEED_MARKER}",  "id": 9999000001},
    {"nombre": "Seed Reporter1", "correo": f"reporter1{_SEED_MARKER}", "id": 9999000002},
    {"nombre": "Seed Reporter2", "correo": f"reporter2{_SEED_MARKER}", "id": 9999000003},
    {"nombre": "Seed Votante1",  "correo": f"votante1{_SEED_MARKER}",  "id": 9999000004},
    {"nombre": "Seed Votante2",  "correo": f"votante2{_SEED_MARKER}",  "id": 9999000005},
]


@router.post("/seed")
def seed_moderation(db: Session = Depends(get_db), _=Depends(_check_secret)):
    """
    Crea usuarios de prueba y un caso de moderación abierto.
    Devuelve los tokens de cada usuario listos para usar en /docs.
    Solo disponible con APP_ENV=development.
    """
    tokens = {}

    # Insertar usuarios (ignorar si ya existen)
    for u in SEED_USERS:
        db.execute(text("""
            INSERT IGNORE INTO usuarios (id, nombre, correo, password, status, strikes_count)
            VALUES (:id, :nombre, :correo, :pw, 'NORMAL', 0)
        """), {"id": u["id"], "nombre": u["nombre"], "correo": u["correo"], "pw": _HASH})

    db.commit()

    # Obtener IDs
    ids = {}
    for u in SEED_USERS:
        row = db.execute(
            text("SELECT id FROM usuarios WHERE correo = :c"), {"c": u["correo"]}
        ).fetchone()
        if not row:
            raise HTTPException(status_code=500, detail=f"No se pudo crear {u['correo']}")
        ids[u["correo"]] = row.id
        tokens[u["nombre"]] = genTokenUser(row.id)

    # Poner al objetivo en EN_REVISION
    objetivo_id = ids[f"objetivo{_SEED_MARKER}"]
    db.execute(text("""
        UPDATE usuarios SET status = 'EN_REVISION' WHERE id = :id
    """), {"id": objetivo_id})

    # Crear caso abierto si no existe
    existing = db.execute(text("""
        SELECT id FROM user_moderation_cases
        WHERE target_id = :id AND status = 'OPEN'
    """), {"id": objetivo_id}).fetchone()

    case_id = None
    if not existing:
        db.execute(text("""
            INSERT INTO user_moderation_cases (target_id, status, voting_deadline)
            VALUES (:id, 'OPEN', DATE_ADD(NOW(), INTERVAL 24 HOUR))
        """), {"id": objetivo_id})
        db.commit()
        case_id = db.execute(text("""
            SELECT id FROM user_moderation_cases
            WHERE target_id = :id AND status = 'OPEN'
        """), {"id": objetivo_id}).fetchone().id
    else:
        case_id = existing.id

    db.commit()

    return {
        "status":   "success",
        "password": _PASSWORD,
        "case_id":  case_id,
        "tokens":   tokens,
        "nota":     "Usa el token en el botón Authorize de /docs como: Bearer <token>"
    }


@router.delete("/cleanup")
def cleanup_seed(db: Session = Depends(get_db), _=Depends(_check_secret)):
    """Elimina todos los datos de prueba generados por /dev/seed."""
    seed_ids = db.execute(text("""
        SELECT id FROM usuarios WHERE correo LIKE :marker
    """), {"marker": f"%{_SEED_MARKER}%"}).fetchall()

    if not seed_ids:
        return {"status": "success", "eliminados": 0}

    id_list = tuple(r.id for r in seed_ids)

    db.execute(text("DELETE FROM user_moderation_votes WHERE voter_id IN :ids"),   {"ids": id_list})
    db.execute(text("DELETE FROM user_moderation_cases WHERE target_id IN :ids"),  {"ids": id_list})
    db.execute(text("DELETE FROM user_reports WHERE reporter_id IN :ids OR reported_id IN :ids"),
               {"ids": id_list})
    db.execute(text("DELETE FROM usuarios WHERE id IN :ids"), {"ids": id_list})
    db.commit()

    return {"status": "success", "eliminados": len(id_list)}
