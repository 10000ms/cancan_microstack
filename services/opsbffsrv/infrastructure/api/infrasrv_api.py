"""
InfraSrv API 客户端 / InfraSrv API Client

用于调用 infrasrv 的内部接口和服务管理接口 / For calling infrasrv internal and service management interfaces
"""
from typing import (
    Optional,
)
import os
import http

from linglong_web.utils import logger
from linglong_web import LinglongConfig
from linglong_web import (
    HTTPClientConfig,
    http_client,
)
from cancan_microstack.public.api.infrasrv_client import InfraSrvApiClient
from cancan_microstack.public.error import HTTPException
from cancan_microstack.public.const.error import ErrorCode
from cancan_microstack.public.schemas.infra.service_management import (
    ServiceManagementRequest,
    ServiceManagementAPIResponse,
)
from cancan_microstack.public.schemas.infra.operation import (
    OperationCreateRequest,
    OperationUpdateRequest,
)


class InfraSrvApi(InfraSrvApiClient):
    """
    用于与 InfraSrv 通信的 API 客户端 / API client for communicating with InfraSrv
    继承自 InfraSrvApiClient，提供配置注入 / Inherits from InfraSrvApiClient with configuration injection
    
    继承的方法 / Inherited methods:
    - create_operation(request: OperationCreateRequest) -> Dict[str, Any]
    - update_operation(request: OperationUpdateRequest) -> Dict[str, Any]
    - get_operation(operation_id: str) -> Dict[str, Any]
    - list_operations(service_name, status, limit, offset) -> Dict[str, Any]
    
    新增方法（服务管理）/ New methods (service management):
    - start_service(request: ServiceManagementRequest) -> Dict[str, Any]
    - stop_service(request: ServiceManagementRequest) -> Dict[str, Any]
    - restart_service(request: ServiceManagementRequest) -> Dict[str, Any]
    """

    def __init__(self):
        # 注意：该类可能会在 LinglongConfig 初始化前被 import。
        # Note: This class may be imported before LinglongConfig is initialized.
        config_host = getattr(LinglongConfig, "INFRASRV_HOST", None)
        infrasrv_host = os.getenv(
            "INFRASRV_HOST",
            config_host or "http://infrasrv.service:8080",
        )

        base_url = f"{infrasrv_host}"
        super().__init__(base_url)
        self._internal_base_url = f"{infrasrv_host}/v1/infrasrv/internal"
        self.service_mgmt_base_url = f"{infrasrv_host}/v1/infrasrv/service"
        logger.info(f"InfraSrvApi initialized (opsbffsrv) with base_url: {base_url}")
        logger.info(f"Service management base URL: {self.service_mgmt_base_url}")
        logger.info(f"Internal base URL: {self._internal_base_url}")

    async def create_operation(self, request: OperationCreateRequest):
        """创建操作记录（内部接口）/ Create operation via internal API."""
        json_data = request.model_dump(mode="json")
        return await self._make_request(
            http.HTTPMethod.POST,
            "/v1/infrasrv/internal/operation/create",
            json_data=json_data,
            response_models=self.OPERATION_RESPONSE_MODELS,
        )

    async def update_operation(self, request: OperationUpdateRequest):
        """更新操作记录（内部接口）/ Update operation via internal API."""
        json_data = request.model_dump(mode="json", exclude_none=True)
        if request.started_at:
            json_data["started_at"] = request.started_at.isoformat()
        if request.completed_at:
            json_data["completed_at"] = request.completed_at.isoformat()
        return await self._make_request(
            http.HTTPMethod.POST,
            "/v1/infrasrv/internal/operation/update",
            json_data=json_data,
            response_models=self.OPERATION_RESPONSE_MODELS,
        )

    async def get_operation(self, operation_id: str):
        """获取操作记录（内部接口）/ Get operation via internal API."""
        return await self._make_request(
            http.HTTPMethod.GET,
            "/v1/infrasrv/internal/operation/get",
            params={"operation_id": operation_id},
            response_models=self.OPERATION_RESPONSE_MODELS,
        )

    async def list_operations(
            self,
            service_name: Optional[str] = None,
            status: Optional[str] = None,
            limit: int = 50,
            offset: int = 0,
    ):
        """列出操作记录（内部接口）/ List operations via internal API."""
        params: dict[str, object] = {"limit": limit, "offset": offset}
        if service_name:
            params["service_name"] = service_name
        if status:
            params["status"] = status
        return await self._make_request(
            http.HTTPMethod.GET,
            "/v1/infrasrv/internal/operation/list",
            params=params,
            response_models=self.OPERATION_LIST_MODELS,
        )

    async def _make_service_management_request(
            self,
            endpoint: str,
            request: ServiceManagementRequest
    ) -> ServiceManagementAPIResponse:
        """
        调用 infrasrv 服务管理接口的通用方法 / Generic method for calling infrasrv service management interfaces
        
        Args:
            endpoint: API 端点（如 /start, /stop）/ API endpoint (e.g., /start, /stop)
            request: 服务管理请求 / Service management request
        
        Returns:
            ServiceManagementAPIResponse
        
        Raises:
            HTTPException: 调用失败时抛出异常 / Raise exception on call failure
        """
        url = f"{self.service_mgmt_base_url}{endpoint}"
        json_data = request.model_dump(mode='json')

        try:
            resp = await http_client.post(
                url=url,
                json=json_data,
                timeout=HTTPClientConfig.INTERNAL_SERVICE_TIMEOUT
            )

            if resp and resp.status == 200:
                response_json = await resp.json()
                logger.debug(f"Successfully called infrasrv service management API [{endpoint}]")

                # 处理 infrasrv 的标准响应格式 / Handle infrasrv's standard response format
                if isinstance(response_json, dict) and "success" in response_json:
                    if response_json.get("success"):
                        data = response_json.get("data", {})
                        # 将 dict 转换为 model / Convert dict to model
                        try:
                            return ServiceManagementAPIResponse(**data)
                        except Exception as e:
                            logger.error(f"Failed to parse response as ServiceManagementAPIResponse: {e}")
                            raise HTTPException(
                                status_code=http.HTTPStatus.INTERNAL_SERVER_ERROR.value,
                                error_code=ErrorCode.SYSTEM_ERROR,
                                msg=f"Failed to parse response from infrasrv: {str(e)}"
                            )
                    else:
                        error_info = response_json.get("error", {})
                        error_msg = error_info.get("msg", "Unknown error") if isinstance(error_info, dict) else str(
                            error_info)
                        error_code = error_info.get("code", ErrorCode.SYSTEM_ERROR) if isinstance(error_info,
                                                                                                  dict) else ErrorCode.SYSTEM_ERROR
                        logger.error(f"infrasrv returned error: {error_msg}")
                        raise HTTPException(
                            status_code=http.HTTPStatus.INTERNAL_SERVER_ERROR.value,
                            error_code=error_code,
                            msg=f"Infrasrv error: {error_msg}"
                        )
                else:
                    logger.error(f"Unexpected response format from infrasrv: {response_json}")
                    raise HTTPException(
                        status_code=http.HTTPStatus.INTERNAL_SERVER_ERROR.value,
                        error_code=ErrorCode.SYSTEM_ERROR,
                        msg=f"Unexpected response format from infrasrv"
                    )
            else:
                status_code = resp.status if resp else 500
                error_msg = f"HTTP error: {status_code}"
                logger.error(f"Failed to call infrasrv service management API [{endpoint}]: {error_msg}")
                raise HTTPException(
                    status_code=status_code,
                    error_code=ErrorCode.NETWORK_ERROR,
                    msg=f"Failed to call infrasrv: {error_msg}"
                )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error calling infrasrv service management API [{endpoint}]: {e}", exc_info=True)
            raise HTTPException(
                status_code=http.HTTPStatus.INTERNAL_SERVER_ERROR.value,
                error_code=ErrorCode.SYSTEM_ERROR,
                msg=f"Error calling infrasrv: {str(e)}"
            )

    async def start_service(self, request: ServiceManagementRequest) -> ServiceManagementAPIResponse:
        """
        调用 infrasrv 启动服务 / Call infrasrv to start service
        
        Args:
            request: 服务管理请求 / Service management request
        
        Returns:
            ServiceManagementAPIResponse 或 None / ServiceManagementAPIResponse or None
        """
        logger.info(
            f"[opsbffsrv → infrasrv] Starting service: {request.service_name}, operation_id: {request.operation_id}")
        return await self._make_service_management_request("/start", request)

    async def stop_service(self, request: ServiceManagementRequest) -> ServiceManagementAPIResponse:
        """
        调用 infrasrv 停止服务 / Call infrasrv to stop service
        
        Args:
            request: 服务管理请求 / Service management request
        
        Returns:
            操作结果 / Operation result
        """
        logger.info(
            f"[opsbffsrv → infrasrv] Stopping service: {request.service_name}, operation_id: {request.operation_id}")
        return await self._make_service_management_request("/stop", request)

    async def restart_service(self, request: ServiceManagementRequest) -> ServiceManagementAPIResponse:
        """
        调用 infrasrv 重启服务 / Call infrasrv to restart service
        
        Args:
            request: 服务管理请求 / Service management request
        
        Returns:
            ServiceManagementAPIResponse 或 None / ServiceManagementAPIResponse or None
        """
        logger.info(
            f"[opsbffsrv → infrasrv] Restarting service: {request.service_name}, operation_id: {request.operation_id}")
        return await self._make_service_management_request("/restart", request)
