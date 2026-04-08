import os
import jwt
from fastapi import HTTPException, Header
from datetime import datetime, timedelta, timezone
from passlib.context import CryptContext
from dotenv import load_dotenv, find_dotenv

# Load environment variables from .env file
load_dotenv(find_dotenv())

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    print("WARNING: SECRET_KEY not found in environment variables!")
    # For testing purposes, set a default if missing, but in production this should be a critical error
    SECRET_KEY = "fodes_default_secret_key_change_me"

print(f"SECRET_KEY loaded: {SECRET_KEY[:5]}...")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
ACCESS_TOKEN_EXPIRE_MINUTES = 60*24
ALGORITHM = "HS256"


def verifyPassword(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def genHashPassword(password):
    return pwd_context.hash(password)


def genTokenUser(user_id):
    tiempo_expiracion = datetime.now(
        timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    payload = {
        "id_usuario": user_id,
        "exp": tiempo_expiracion
    }
    access_token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return access_token


async def verifySession(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Token de sesión no proporcionado o formato inválido"
        )
    token = authorization.split(" ")[1]
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        id_usuario = payload.get("id_usuario")
        if id_usuario is None:
            raise HTTPException(
                status_code=401,
                detail="El token es válido pero no contiene la información del usuario"
            )
        return id_usuario
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=401, detail="El token de sesión ha expirado")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token de sesión inválido")
