from pydantic import BaseModel, ConfigDict

#bắt lỗi typo trong schema nhỏ
class StrictSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")