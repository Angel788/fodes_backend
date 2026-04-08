from pydantic import BaseModel
from typing import List, Optional
from fastapi import Query


class PublicationsConsult(BaseModel):
    cid: str = Query(None)
    categoria: Optional[str] = Query(None)
    tags: Optional[List[str]] = Query(None)
