from linglong_web.utils import logger
from cancan_microstack.services.infrasrv.application.health_check_app import HealthCheckApp

_health_check_app = HealthCheckApp()


async def health_check_task():
    """
    定期健康检查任务
    
    支持：
    - 多实例健康检查
    - 操作窗口期豁免
    - 区分正常/异常关闭
    - 自动重启不健康实例
    """
    try:
        logger.info("Running scheduled health check (multi-instance)...")
        result = await _health_check_app.check_all_instances()

        logger.info(
            f"Health check completed: {result.healthy} healthy, "
            f"{result.degraded} degraded, {result.unhealthy} unhealthy, "
            f"{result.exempted} exempted, {result.expected_stopped} expected_stopped"
        )
    except Exception as e:
        logger.error(f"Error in health check task: {e}", exc_info=True)
