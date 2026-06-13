"""
Pydantic models for asynchronous operations in opsbffsrv.
"""
from pydantic import (
    BaseModel,
    Field,
)

from cancan_microstack.public.const.operation_consts import OperationStatus


class AsyncOperationResponse(BaseModel):
    """Response model for submitting an asynchronous operation."""
    operation_id: str = Field(..., description="The unique ID of the submitted operation.")
    status: OperationStatus = Field(..., description="The initial status of the operation.")
    message: str = Field(..., description="A message indicating the result of the submission.")
    service_name: str = Field(..., description="The full name of the target service.")
