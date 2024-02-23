from pydantic import BaseModel


class URLBase(BaseModel):
    target_url: str

    class Config:
        orm_mode = True


class URL(URLBase):
    is_active: bool
    clicks: int


class URLInfo(URL):
    url: str
    admin_url: str
