"""
异步操作管理应用层 / Asynchronous Operation Management Application Layer

职责 / Responsibilities:
1. 生成 operation_id / Generate operation_id
2. 构造服务管理请求 / Construct service management request
3. 调用 infrasrv 统一服务管理接口 / Call infrasrv unified service management interface
4. 返回操作响应 / Return operation response

重构说明 / Refactoring Notes:
- 移除直接调用 controllersrv 的逻辑 / Removed direct controllersrv calls
- 所有服务管理操作统一通过 infrasrv / All service management operations go through infrasrv
- infrasrv 负责操作记录管理和 controllersrv 调用 / infrasrv handles operation records and controllersrv calls
"""
from typing import (
    Optional,
    Dict,
    Any,
)
from nanoid import generate

from linglong_web.utils import logger
from cancan_microstack.services.opsbffsrv.infrastructure.api.infrasrv_api import InfraSrvApi
from cancan_microstack.public.schemas.infra.service_management import (
    ServiceManagementRequest,
    ServiceManagementAPIResponse,
)
from cancan_microstack.public.const.operation_consts import (
    OperationType,
    OperationStatus,
    InitiatedBy,
    InitiatedFrom,
)
from cancan_microstack.public.schemas.opsbffsrv.async_ops import AsyncOperationResponse


class AsyncOperationApp:
    """
    异步操作管理应用层 / Asynchronous Operation Management Application Layer
    
    简化后的职责：构造请求 → 调用 infrasrv → 返回响应
    Simplified responsibility: Construct request → Call infrasrv → Return response
    """

    def __init__(self):
        # 移除 controllersrv_api，只保留 infrasrv_api / Remove controllersrv_api, keep only infrasrv_api
        self.infrasrv_api = InfraSrvApi()

    async def submit_operation(
            self,
            operation_type: OperationType,
            service_name: str,
            operation_params: Dict[str, Any],
            initiated_by: InitiatedBy = InitiatedBy.OPSBFFSRV,
            initiated_from: InitiatedFrom = InitiatedFrom.FRONTEND
    ) -> AsyncOperationResponse:
        """
        提交异步操作（统一通过 infrasrv）/ Submit asynchronous operation (unified through infrasrv)

        1. 生成 operation_id / Generate operation_id
        2. 构造 ServiceManagementRequest / Construct ServiceManagementRequest
        3. 调用 infrasrv 统一服务管理接口 / Call infrasrv unified service management interface
        4. infrasrv 内部完成：创建记录 → 调用 controllersrv → 更新状态 / infrasrv internally: Create record → Call controllersrv → Update status
        5. 返回响应 / Return response
        
        Args:
            operation_type: 操作类型 / Operation type
            service_name: 服务名称 / Service name
            operation_params: 操作参数 / Operation parameters
            initiated_by: 操作发起者 / Operation initiator
            initiated_from: 发起来源 / Initiation source
        
        Returns:
            异步操作响应 / Asynchronous operation response
        """
        # 步骤 1: 生成 operation_id / Step 1: Generate operation_id
        operation_id = f"op_{operation_type.value}_{generate(size=12)}"
        full_service_name = service_name if service_name.endswith('.service') else f"{service_name}.service"

        logger.info(
            f"[AsyncOperationApp] Submitting operation: "
            f"operation_id={operation_id}, "
            f"type={operation_type.value}, "
            f"service={full_service_name}"
        )

        # 步骤 2: 构造服务管理请求 / Step 2: Construct service management request
        request = ServiceManagementRequest(
            operation_id=operation_id,
            service_name=full_service_name,
            operation_type=operation_type,
            operation_params=operation_params,
            initiated_by=initiated_by,
            initiated_from=initiated_from
        )

        # 步骤 3: 调用 infrasrv（根据操作类型分派）/ Step 3: Call infrasrv (dispatch by operation type)
        # 此时如果失败会抛出异常 / If failed, exception will be raised
        api_response = await self._call_infrasrv(operation_type, request)

        # 步骤 4: 处理 infrasrv 响应 / Step 4: Handle infrasrv response
        # 成功获得响应 / Successfully got response
        # 将字符串状态转换为 OperationStatus 枚举 / Convert string status to OperationStatus enum
        try:
            status = OperationStatus(api_response.status)
        except ValueError:
            status = OperationStatus.PENDING

        logger.info(
            f"[AsyncOperationApp] Operation {operation_id} submitted successfully, status: {status.value}")

        return AsyncOperationResponse(
            operation_id=api_response.operation_id,
            status=status,
            message=api_response.message or f"Operation submitted: {operation_type.value} {full_service_name}",
            service_name=api_response.service_name
        )

    async def _call_infrasrv(
            self,
            operation_type: OperationType,
            request: ServiceManagementRequest
    ) -> 'ServiceManagementAPIResponse':
        """
        调用 infrasrv 执行服务管理操作 / Call infrasrv to execute service management operation
        
        根据操作类型分派到不同的 infrasrv API / Dispatch to different infrasrv APIs based on operation type
        
        Args:
            operation_type: 操作类型 / Operation type
            request: 服务管理请求 / Service management request
        
        Returns:
            ServiceManagementAPIResponse
        """
        logger.info(
            f"[AsyncOperationApp → infrasrv] Calling infrasrv for {operation_type.value} operation: {request.operation_id}"
        )

        if operation_type == OperationType.START:
            return await self.infrasrv_api.start_service(request)

        elif operation_type == OperationType.STOP:
            return await self.infrasrv_api.stop_service(request)

        elif operation_type == OperationType.RESTART:
            return await self.infrasrv_api.restart_service(request)

        else:
            raise ValueError(f"Unsupported operation type: {operation_type}")
