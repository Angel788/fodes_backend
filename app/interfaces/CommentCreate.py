from pydantic import BaseModel
from typing import List, Optional


class CommentCreate(BaseModel):
    titulo: str
    publication_cid: str
    contenido: str
    parent_cid: Optional[str] = None
    tags: Optional[List[int]] = []
