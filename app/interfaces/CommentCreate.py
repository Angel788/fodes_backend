from pydantic import BaseModel
from typing import List, Optional


class CommentCreate(BaseModel):
    titulo: str
    publication_cid: str
    contenido: str
    tags: Optional[List[int]] = []
