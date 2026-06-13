"""
健康检查 API

支持多实例健康检查
"""
from linglong_web import build_success_response
from cancan_microstack.public.schemas.common import APIResponse
from cancan_microstack.services.infrasrv.application.health_check_app import HealthCheckApp

_health_check_app = HealthCheckApp()


async def health_check_all_instances_handler() -> APIResponse[dict | None]:
    """
    对所有实例进行健康检查
    
    功能：
    - 支持多实例检查
    - 操作窗口期豁免
    - 区分正常/异常关闭
    - 自动重启不健康实例
    
    Returns:
        健康检查结果汇总
    """
    result = await _health_check_app.check_all_instances()

    # 在 handler 层将 Pydantic model 序列化为 dict/JSON
    return build_success_response(data=result.model_dump())
