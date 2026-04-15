from pydantic import BaseModel


class UserResetPassword(BaseModel):
    correo: str
    new_password: str
    nombre_saes: str  # nombre devuelto por SAES para verificar identidad
