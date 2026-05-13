from pydantic import BaseModel


class UserLogin(BaseModel):
    boleta: str
    password: str
