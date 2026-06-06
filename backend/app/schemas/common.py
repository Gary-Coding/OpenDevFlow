from pydantic import BaseModel


class MessageResponse(BaseModel):
    message: str


class PageResponse(BaseModel):
    items: list[dict]
    total: int

