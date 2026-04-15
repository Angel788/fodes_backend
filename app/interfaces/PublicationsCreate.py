from pydantic import BaseModel
from typing import List


class PublicationCreate(BaseModel):
    cid_content: str
    title: str
    content: str
    tags: List[str]
    category: str
