"""
预注册钩子
使用预注册钩子机制扩展服务注册功能
"""
from typing import (
    Dict,
    Any,
)
from datetime import (
    datetime,
    timezone,
)

from .pre_registration_hooks import (
    BaseHook,
    HookResult,
    HookPriority,
    HookContext,
    HookExecutionResult,
)
from .hook_registry import get_hook_manager
from linglong_web.utils import logger


class ServiceNameValidationHook(BaseHook):
    """服务名称验证钩子
    
    验证服务名称是否符合规范
    """

    def __init__(self):
        super().__init__("service_name_validation", HookPriority.HIGH)

    async def execute(self, context: HookContext) -> HookExecutionResult:
        service_name = context.service_name

        # 验证服务名称不为空
        if not service_name or not service_name.strip():
            return HookExecutionResult(
                hook_name=self.name,
                result=HookResult.FAILURE,
                message="Service name cannot be empty"
            )

        # 验证服务名称格式（只允许字母、数字、下划线和连字符）
        import re
        if not re.match(r'^[a-zA-Z0-9_-]+$', service_name):
            return HookExecutionResult(
                hook_name=self.name,
                result=HookResult.FAILURE,
                message="Service name can only contain letters, numbers, underscores and hyphens"
            )

        # 验证服务名称长度
        if len(service_name) > 50:
            return HookExecutionResult(
                hook_name=self.name,
                result=HookResult.FAILURE,
                message="Service name too long (max 50 characters)"
            )

        return HookExecutionResult(
            hook_name=self.name,
            result=HookResult.SUCCESS,
            message="Service name validation passed"
        )


class HostValidationHook(BaseHook):
    """主机地址验证钩子
    
    验证主机地址是否有效
    """

    def __init__(self):
        super().__init__("host_validation", HookPriority.HIGH)

    async def execute(self, context: HookContext) -> HookExecutionResult:
        host = context.host

        # 验证主机地址不为空
        if not host or not host.strip():
            return HookExecutionResult(
                hook_name=self.name,
                result=HookResult.FAILURE,
                message="Host cannot be empty"
            )

        # 拒绝无效的主机地址
        invalid_hosts = ["unknown", "localhost", "127.0.0.1", "0.0.0.0"]
        if host.lower() in invalid_hosts:
            return HookExecutionResult(
                hook_name=self.name,
                result=HookResult.FAILURE,
                message=f"Invalid host '{host}'. Please configure proper hostname in docker-compose.yml"
            )

        return HookExecutionResult(
            hook_name=self.name,
            result=HookResult.SUCCESS,
            message="Host validation passed"
        )


class MetadataEnrichmentHook(BaseHook):
    """元数据增强钩子
    
    为服务实例添加额外的元数据
    """

    def __init__(self):
        super().__init__("metadata_enrichment", HookPriority.NORMAL)

    async def execute(self, context: HookContext) -> HookExecutionResult:
        # 获取现有元数据
        metadata = context.metadata
        if not isinstance(metadata, dict):
            metadata = {}

        # 添加注册时间戳
        metadata["registered_at"] = datetime.now(timezone.utc).isoformat()

        # 添加注册来源标识
        metadata["registered_by"] = "infrasrv"

        # 添加服务类型标识（根据服务名称推断）
        service_name = context.service_name
        if "bff" in service_name.lower():
            metadata["service_type"] = "backend-for-frontend"
        elif "srv" in service_name.lower():
            metadata["service_type"] = "microservice"
        else:
            metadata["service_type"] = "unknown"

        # Pydantic models are mutable by default, modifying directly
        context.metadata = metadata

        return HookExecutionResult(
            hook_name=self.name,
            result=HookResult.SUCCESS,
            message="Metadata enriched successfully"
        )


class PortRangeValidationHook(BaseHook):
    """端口范围验证钩子
    
    验证端口号是否在有效范围内
    """

    def __init__(self):
        super().__init__("port_range_validation", HookPriority.NORMAL)

    async def execute(self, context: HookContext) -> HookExecutionResult:
        port = context.port

        # 验证端口号是否为整数
        if not isinstance(port, int):
            try:
                port = int(port)
            except (ValueError, TypeError):
                return HookExecutionResult(
                    hook_name=self.name,
                    result=HookResult.FAILURE,
                    message="Port must be a valid integer"
                )

        # 验证端口范围
        if port < 1024 or port > 65535:
            return HookExecutionResult(
                hook_name=self.name,
                result=HookResult.FAILURE,
                message="Port must be between 1024 and 65535"
            )

        return HookExecutionResult(
            hook_name=self.name,
            result=HookResult.SUCCESS,
            message="Port validation passed"
        )


class ServiceQuotaHook(BaseHook):
    """服务配额检查钩子
    
    检查服务实例数量是否超过配额限制
    """

    def __init__(self):
        super().__init__("service_quota", HookPriority.LOW)
        # 服务配额配置
        self.service_quotas = {
            "default": 10,  # 默认每个服务最多 10 个实例
        }

    async def execute(self, context: HookContext) -> HookExecutionResult:
        service_name = context.service_name

        # 获取服务配额
        quota = self.service_quotas.get(service_name, self.service_quotas["default"])

        # 查询 service registry 中该服务当前已注册的实例数量（真实计数）
        from cancan_microstack.services.infrasrv.infrastructure.db.operate.service_instance_op import (
            count_instances_by_service,
        )
        current_instances = await count_instances_by_service(service_name)

        if current_instances >= quota:
            return HookExecutionResult(
                hook_name=self.name,
                result=HookResult.FAILURE,
                message=f"Service '{service_name}' has reached its quota of {quota} instances"
            )

        return HookExecutionResult(
            hook_name=self.name,
            result=HookResult.SUCCESS,
            message=f"Service quota check passed ({current_instances}/{quota})"
        )


# 函数钩子示例
def function_based_validation_hook(context: HookContext) -> tuple:
    """基于函数的验证钩子示例
    
    验证实例ID格式
    """
    instance_id = context.instance_id

    # 验证实例ID格式
    if "-" not in instance_id:
        return HookResult.FAILURE, "Instance ID must contain a hyphen (-)"

    return HookResult.SUCCESS, "Instance ID validation passed"


# 注册所有钩子
def register_all_hooks():
    """注册所有预注册钩子"""
    hook_manager = get_hook_manager()
    hook_manager.register_hook(ServiceNameValidationHook())
    hook_manager.register_hook(HostValidationHook())
    hook_manager.register_hook(MetadataEnrichmentHook())
    hook_manager.register_hook(PortRangeValidationHook())
    hook_manager.register_hook(ServiceQuotaHook())

    logger.info("All pre-registration hooks registered successfully")


def register_default_hooks(hook_manager):
    """
    注册默认的预注册钩子
    
    Args:
        hook_manager: 钩子管理器实例
    """
    # 注册服务名称验证钩子
    hook_manager.register_hook(ServiceNameValidationHook())

    # 注册主机地址验证钩子
    hook_manager.register_hook(HostValidationHook())

    # 注册元数据增强钩子
    hook_manager.register_hook(MetadataEnrichmentHook())

    # 注册端口范围验证钩子
    hook_manager.register_hook(PortRangeValidationHook())

    # 注册服务配额检查钩子
    hook_manager.register_hook(ServiceQuotaHook())

    logger.info("All default pre-registration hooks have been registered")


# 示例：动态添加钩子
def add_custom_validation_hook(hook_manager, validation_func):
    """
    动态添加自定义验证钩子
    
    Args:
        hook_manager: 钩子管理器实例
        validation_func: 验证函数，接收service_info参数，返回(bool, str)元组
    """

    def custom_hook(context):
        # 简单示例，实际需要根据validation_func的实现调整
        return HookResult.SUCCESS, "Custom validation passed"

    hook_manager.register_hook(custom_hook)
    logger.info("Custom validation hook has been registered")


# 示例：动态移除钩子
def remove_hook_by_type(hook_manager, hook_type):
    """
    根据钩子类型移除钩子
    
    Args:
        hook_manager: 钩子管理器实例
        hook_type: 要移除的钩子类型
    """
    hooks = hook_manager.get_hooks()
    for hook in hooks:
        if type(hook) == hook_type:
            hook_manager.unregister_hook(hook.name)
            logger.info(f"Removed hook of type {hook_type.__name__}")
            return True
    return False
