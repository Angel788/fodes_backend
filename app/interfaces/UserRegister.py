from pydantic import BaseModel


class UserRegister(BaseModel):
    nombre: str
    correo: str
    password: str
