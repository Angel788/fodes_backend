from fastapi import APIRouter, Depends, Request, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.db.database import get_db
from app.auth.auth import genHashPassword, verifyPassword, genTokenUser
from app.interfaces.UserLogin import UserLogin
from app.interfaces.UserRegister import UserRegister
from app.interfaces.UserResetPassword import UserResetPassword

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
        # Check if user exists and verify password
        query_user = text("SELECT id, password FROM usuarios WHERE correo = :correo")
        user = db.execute(query_user, {"correo": user_data.correo}).fetchone()
        
        if not user or not verifyPassword(user_data.password, user.password):
            raise HTTPException(
                status_code=401,
                detail="Correo o contraseña incorrectos",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Generate JWT token with user ID
        access_token = genTokenUser(user.id)
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "message": "Inicio de sesión exitoso"
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
    Registers a new user in the system.
    - **nombre**: Full name.
    - **correo**: Unique email address.
    - **password**: Plain text password (will be hashed).
    """
    try:
        # Check if email is already taken
        query_check = text("SELECT id FROM usuarios WHERE correo = :correo")
        existing_user = db.execute(query_check, {"correo": user_data.correo}).fetchone()

        if existing_user:
            raise HTTPException(
                status_code=400,
                detail="El correo electrónico ya está registrado."
            )
            
        # Hash password and insert user
        hashed_password = genHashPassword(user_data.password)
        query_insert = text("""
            INSERT INTO usuarios (nombre, correo, password) 
            VALUES (:nombre, :correo, :password_hash) 
        """)

        result = db.execute(query_insert, {
            "nombre": user_data.nombre,
            "correo": user_data.correo,
            "password_hash": hashed_password
        })
        new_user_id = result.lastrowid
        db.commit()
        
        return {
            "status": "success",
            "message": "Usuario registrado exitosamente",
            "data": {
                "id_usuario": new_user_id,
                "correo": user_data.correo
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error interno al registrar: {str(e)}")


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
            raise HTTPException(status_code=404, detail="No existe una cuenta con ese correo")

        # Verify that SAES name contains all words from the stored name
        tokens_saes = _normalizar(data.nombre_saes).split()
        tokens_db   = _normalizar(user.nombre).split()
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
