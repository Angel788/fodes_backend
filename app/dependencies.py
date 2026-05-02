from sqlalchemy.orm import Session
from sqlalchemy import text
from fastapi import Depends, HTTPException

from app.db.database import get_db
from app.auth.auth import verifySession


def recover_suspension(db: Session, user_id: str) -> None:
    """Si la suspensión temporal venció, restaura al usuario a NORMAL."""
    db.execute(text("""
        UPDATE usuarios
        SET status='NORMAL', ban_until=NULL
        WHERE id=:id AND status='SUSPENDIDO' AND ban_until IS NOT NULL AND ban_until <= NOW()
    """), {"id": user_id})
    db.commit()


async def verifyActiveSession(
    db: Session = Depends(get_db),
    id_user: str = Depends(verifySession),
) -> str:
    """verifySession + auto-recupera suspensiones vencidas + bloquea suspendidos/baneados."""
    recover_suspension(db, id_user)
    row = db.execute(
        text("SELECT status FROM usuarios WHERE id=:id"), {"id": id_user}
    ).fetchone()
    if row and row.status == 'SUSPENDIDO':
        raise HTTPException(status_code=403, detail="Tu cuenta está suspendida temporalmente.")
    if row and row.status == 'BANEADO':
        raise HTTPException(status_code=403, detail="Tu cuenta ha sido baneada permanentemente.")
    return id_user
