from pydantic import BaseModel


class UserLogin(BaseModel):
    correo: str
    password: str
