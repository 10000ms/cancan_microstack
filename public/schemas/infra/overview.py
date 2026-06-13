"""
Service overview related Pydantic models.
"""
from pydantic import BaseModel

from cancan_microstack.public.const.health_consts import (
    HealthOverallStatus,
    ServiceRuntimeStatus,
)


class ServiceOverview(BaseModel):
    """Service overview data model."""
    service_name: str
    description: str = ""
    service_type: str = "business"
    expected_status: ServiceRuntimeStatus = ServiceRuntimeStatus.RUNNING
    actual_status: ServiceRuntimeStatus = ServiceRuntimeStatus.STOPPED
    status_matches_expected: bool = False
    desired_replicas: int = 1
    actual_replicas: int = 0
    total_instances: int = 0
    healthy_instances: int = 0
    unhealthy_instances: int = 0
    overall_status: HealthOverallStatus = HealthOverallStatus.DOWN