from pydantic import BaseModel

class UserRegister(BaseModel):
    nombre: str
    correo: str
    password: str
    boleta: str
    url_saes: str
