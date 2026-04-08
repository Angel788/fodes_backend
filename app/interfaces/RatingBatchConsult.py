from pydantic import BaseModel
from typing import List


class RatingBatchConsult(BaseModel):
    cids: List[str]
