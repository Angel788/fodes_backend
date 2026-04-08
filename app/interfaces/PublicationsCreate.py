from pydantic import BaseModel
from typing import List


class PublicationCreate(BaseModel):
    title: str
    content: str
    tags: List[str]
    category: str
