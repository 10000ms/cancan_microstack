from linglong_web.utils import logger
from cancan_microstack.services.infrasrv.application.service_registry import ServiceRegistryApp

_service_registry_app = ServiceRegistryApp()


async def cleanup_dead_instances_task():
    """定期清理已下线的服务实例"""
    try:
        logger.info("Running scheduled cleanup of dead service instances...")
        await _service_registry_app.cleanup_dead_instances()
    except Exception as e:
        logger.error(f"Error in cleanup task: {e}", exc_info=True)
