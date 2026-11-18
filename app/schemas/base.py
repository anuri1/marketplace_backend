from pydantic import BaseModel, ConfigDict


class ReadModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class CreateModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
