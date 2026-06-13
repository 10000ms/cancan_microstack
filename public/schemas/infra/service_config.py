from pydantic import (
    BaseModel,
    Field,
)


class ServiceConfig(BaseModel):
    service_name: str = Field(..., description="The name of the service")
    conf_key: str = Field(..., description="The configuration key")
    conf_value: str = Field(..., description="The configuration value")
