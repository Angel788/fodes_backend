from pydantic import BaseModel, Field


class CommentVote(BaseModel):
    cid_content: str
    vote: int = Field(ge=0, le=5)
