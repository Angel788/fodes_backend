from fastapi import APIRouter, Depends, Request, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.db.database import get_db
from app.auth.auth import genHashPassword, verifyPassword, genTokenUser
from app.interfaces.UserLogin import UserLogin
from app.interfaces.UserRegister import UserRegister
from app.auth.saes import validar_desde_url
from app.interfaces.UserResetPassword import UserResetPassword
from app.dependencies import verifyActiveSession
from pydantic import BaseModel

router = APIRouter(prefix="", tags=["Authentication"])
limiter = Limiter(key_func=get_remote_address)


@router.post("/login")
@limiter.limit("5/minute")
async def login(
    request: Request,
    user_data: UserLogin,
    db: Session = Depends(get_db)
):
    """
    Authenticates a user and returns a JWT access token.
    - **correo**: User email.
    - **password**: User password.
    """
    try:
        from datetime import datetime
        # Check if user exists and verify password
        query_user = text(
            "SELECT id, nombre, password, status, ban_until, created_at FROM usuarios WHERE correo = :correo")
        user = db.execute(query_user, {"correo": user_data.correo}).fetchone()

        if not user or not verifyPassword(user_data.password, user.password):
            raise HTTPException(
                status_code=401,
                detail="Correo o contraseña incorrectos",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Auto-recuperar suspensión temporal vencida
        if user.status == 'SUSPENDIDO' and user.ban_until and user.ban_until <= datetime.now():
            db.execute(text(
                "UPDATE usuarios SET status='NORMAL', ban_until=NULL WHERE id=:id"
            ), {"id": user.id})
            db.commit()
            status_actual = 'NORMAL'
        else:
            status_actual = user.status

        # Verificar antigüedad de boleta (10 semestres = 5 años)
        año_ingreso = int(str(user.id)[:4])
        if datetime.now().year >= año_ingreso + 5 and status_actual not in ('BANEADO',):
            db.execute(text(
                "UPDATE usuarios SET status='SUSPENDIDO', ban_until=NULL WHERE id=:id AND status != 'BANEADO'"
            ), {"id": user.id})
            db.commit()
            raise HTTPException(
                status_code=403,
                detail="Tu tiempo en la plataforma ha concluido (más de 10 semestres). Tu cuenta ha sido suspendida de forma indefinida.",
            )

        if status_actual == 'BANEADO':
            raise HTTPException(status_code=403, detail="Tu cuenta ha sido baneada permanentemente de la plataforma.")

        # Generate JWT token with user ID
        access_token = genTokenUser(user.id)
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "nombre": user.nombre,
            "fecha_registro": user.created_at.strftime("%d/%m/%Y") if user.created_at else None,
            "status": status_actual,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")


@router.post("/register")
@limiter.limit("5/minute")
async def register(
    request: Request,
    user_data: UserRegister,
    db: Session = Depends(get_db)
):
    """
    Registers a new student in the system.
    - **nombre**: Full name.
    - **correo**: Unique email address.
    - **password**: Plain text password.
    - **boleta**: Student ID (used as primary key).
    - **url_saes**: Mandatory URL from SAES QR.
    """
    try:
        # Check if email or id (boleta) is already taken
        query_check = text(
            "SELECT id FROM usuarios WHERE correo = :correo OR id = :boleta")
        existing_user = db.execute(query_check, {
            "correo": user_data.correo,
            "boleta": user_data.boleta
        }).fetchone()

        if existing_user:
            raise HTTPException(
                status_code=400,
                detail="El correo electrónico o la boleta ya están registrados."
            )

        # Bloquear boletas con más de 10 semestres (5 años)
        from datetime import datetime
        año_ingreso = int(str(user_data.boleta)[:4])
        if datetime.now().year >= año_ingreso + 5:
            raise HTTPException(
                status_code=400,
                detail="No es posible registrarse: tu boleta indica más de 10 semestres en la institución.",
            )

        # Validación SAES obligatoria
        try:
            resultado = await validar_desde_url(user_data.boleta, user_data.url_saes)
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Error de verificación SAES: {str(e)}"
            )
        if not resultado:
            raise HTTPException(
                status_code=400,
                detail="No se pudo verificar la identidad en SAES."
            )

        # Hash password and insert user
        hashed_password = genHashPassword(user_data.password)
        query_insert = text("""
            INSERT INTO usuarios (id, nombre, correo, password)
            VALUES (:boleta, :nombre, :correo, :password_hash)
        """)

        db.execute(query_insert, {
            "boleta": user_data.boleta,
            "nombre": user_data.nombre,
            "correo": user_data.correo,
            "password_hash": hashed_password,
        })
        db.commit()
        return {
            "status": "success",
            "message": "Usuario registrado y verificado exitosamente",
            "data": {
                "id_usuario": user_data.boleta,
                "correo": user_data.correo,
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500, detail=f"Error interno al registrar: {str(e)}")


def _normalizar(s: str) -> str:
    import unicodedata
    s = unicodedata.normalize('NFD', s)
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
    return s.lower().replace('-', ' ')


@router.post("/reset-password")
@limiter.limit("5/minute")
async def reset_password(
    request: Request,
    data: UserResetPassword,
    db: Session = Depends(get_db)
):
    """
    Resets the password of a user after verifying their identity via SAES name.
    - **correo**: Institutional email.
    - **new_password**: New password (plain text, will be hashed).
    - **nombre_saes**: Full name returned by SAES validation.
    """
    try:
        query = text("SELECT id, nombre FROM usuarios WHERE correo = :correo")
        user = db.execute(query, {"correo": data.correo}).fetchone()

        if not user:
            raise HTTPException(
                status_code=404, detail="No existe una cuenta con ese correo")

        # Verify that SAES name contains all words from the stored name
        tokens_saes = _normalizar(data.nombre_saes).split()
        tokens_db = _normalizar(user.nombre).split()
        coincide = all(t in tokens_saes for t in tokens_db if t)

        if not coincide:
            raise HTTPException(
                status_code=400,
                detail="El nombre del comprobante SAES no coincide con el registrado en tu cuenta"
            )

        hashed = genHashPassword(data.new_password)
        db.execute(
            text("UPDATE usuarios SET password = :pwd WHERE id = :id"),
            {"pwd": hashed, "id": user.id}
        )
        db.commit()

        return {"status": "success", "message": "Contraseña actualizada correctamente"}

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")


class ChangePasswordBody(BaseModel):
    new_password: str


@router.post("/change-password")
async def change_password(
    body: ChangePasswordBody,
    db: Session = Depends(get_db),
    id_user: str = Depends(verifyActiveSession),
):
    if len(body.new_password) < 16 or len(body.new_password) > 24:
        raise HTTPException(status_code=400, detail="La key debe tener entre 16 y 24 caracteres")

    hashed = genHashPassword(body.new_password)
    db.execute(
        text("UPDATE usuarios SET password = :pwd WHERE id = :id"),
        {"pwd": hashed, "id": id_user}
    )
    db.commit()
    return {"status": "success", "message": "Key actualizada correctamente"}
