from pydantic import BaseModel, Field


class PublicationVote(BaseModel):
    cid_content: str
    vote: int = Field(ge=0, le=5)
