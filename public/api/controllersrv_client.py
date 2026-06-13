"""
controllersrv API 客户端 / controllersrv API client
"""
import http
from typing import (
    Any,
    Dict,
    List,
    Optional,
    Sequence,
    Tuple,
    Type,
    Union,
    cast,
)

from pydantic import (
    BaseModel,
    ValidationError,
)

from linglong_web.utils import logger
from linglong_web import (
    http_client,
    HTTPClientConfig,
)
from cancan_microstack.public.schemas.common import (
    APIError,
    APIResponse,
)
from cancan_microstack.public.schemas.controllersrv.responses import (
    EnqueueSuccessResponse,
    EnqueueErrorResponse,
    TaskListResponse,
    TaskStatusResponse,
)
from cancan_microstack.public.schemas.controllersrv.validation import ValidationResult

ServiceOperationResponse = Union[
    EnqueueSuccessResponse,
    EnqueueErrorResponse,
    ValidationResult,
]


class ControllerSrvApiClient:
    """
    用于与 controllersrv 通信的基础客户端 / TableBase client for communicating with controllersrv
    
    提供通用的 HTTP 调用与响应解析逻辑，具体业务端可在子类中扩展
    Provides generic HTTP invocation and response parsing logic for subclasses to extend
    """

    SERVICE_OPERATION_MODELS: Tuple[Type[BaseModel], ...] = (
        EnqueueSuccessResponse,
        EnqueueErrorResponse,
        ValidationResult,
    )
    TASK_STATUS_MODELS: Tuple[Type[BaseModel], ...] = (TaskStatusResponse,)
    TASK_LIST_MODELS: Tuple[Type[BaseModel], ...] = (TaskListResponse,)

    def __init__(self, base_url: str):
        """
        初始化 API 客户端 / Initialise API client
        
        Args:
            base_url: controllersrv 的基础 URL / TableBase URL of controllersrv
        """

        self.base_url = base_url
        logger.info(f"ControllerSrvApiClient initialized with base_url: {self.base_url}")

    async def _make_request(
            self,
            method: http.HTTPMethod,
            endpoint: str,
            json_data: Optional[Dict[str, Any]] = None,
            params: Optional[Dict[str, Any]] = None,
            response_models: Sequence[Type[BaseModel]] = (),
    ) -> APIResponse[Optional[BaseModel]]:
        """
        通用请求方法 / Generic request executor
        
        Args:
            method: HTTP 方法枚举 / HTTP method enum
            endpoint: API 路径 / API path
            json_data: 请求体（POST 使用）/ Request payload for POST
            params: 查询参数（GET 使用）/ Query parameters for GET
            response_models: 可用于解析 data 字段的模型列表
                               Models used to deserialize the data payload
        """

        url = f"{self.base_url}{endpoint}"
        try:
            http_callable = getattr(http_client, method.value.lower())
            response = await http_callable(
                url=url,
                params=params,
                json=json_data,
                timeout=HTTPClientConfig.INTERNAL_SERVICE_TIMEOUT,
            )
        except Exception as exc:
            logger.error(f"Error calling controllersrv API [{endpoint}]: {exc}", exc_info=True)
            return APIResponse(success=False, error=APIError(code="HTTP_EXCEPTION", msg=str(exc)))

        if response is None:
            logger.error(f"Failed to call controllersrv API [{endpoint}]: no response object")
            return APIResponse(success=False, error=APIError(code="HTTP_NO_RESPONSE", msg="No response received"))

        if response.status != 200:
            error_message = f"HTTP error: {response.status}"
            logger.error(f"controllersrv API [{endpoint}] returned non-200 status: {response.status}")
            return APIResponse(success=False, error=APIError(code=str(response.status), msg=error_message))

        try:
            payload = await response.json()
        except Exception as exc:
            logger.error(f"Failed to parse controllersrv response JSON for [{endpoint}]: {exc}", exc_info=True)
            return APIResponse(success=False, error=APIError(code="JSON_DECODE_ERROR", msg=str(exc)))

        if not isinstance(payload, dict):
            logger.error(f"Unexpected controllersrv response format for [{endpoint}]: {payload}")
            return APIResponse(success=False, error=APIError(code="INVALID_PAYLOAD", msg="Response is not a dict"))

        success = bool(payload.get("success"))
        error_content = payload.get("error") or {}
        api_error = self._create_api_error(error_content)
        raw_data = payload.get("data")
        parsed_data = self._parse_response_data(raw_data, response_models, endpoint)

        if parsed_data is None and raw_data is not None and response_models:
            logger.error(
                "Failed to parse controllersrv response data for [%s]: %s",
                endpoint,
                raw_data,
            )

        logger.debug(
            "controllersrv API [%s] completed: success=%s, code=%s",
            endpoint,
            success,
            api_error.code,
        )

        return APIResponse(success=success, error=api_error, data=parsed_data)

    @staticmethod
    def _create_api_error(error_content: Any) -> APIError:
        """构造 APIError 对象 / Build APIError object"""

        if isinstance(error_content, dict):
            code = str(error_content.get("code", "50000"))
            msg = str(error_content.get("msg", ""))
        else:
            code = "50000"
            msg = str(error_content) if error_content is not None else ""
        return APIError(code=code, msg=msg)

    def _parse_response_data(
            self,
            data: Any,
            response_models: Sequence[Type[BaseModel]],
            endpoint: str,
    ) -> Optional[BaseModel]:
        """
        将 data 字段反序列化为 Pydantic 模型 / Deserialize data payload into Pydantic model
        """

        if data is None or not response_models:
            return None

        if not isinstance(data, (dict, list)):
            logger.error(f"controllersrv API [{endpoint}] returned non-serialisable data: {data}")
            return None

        for model in response_models:
            try:
                if isinstance(data, model):
                    return data
                return model.model_validate(data)
            except ValidationError:
                continue

        return None

    async def restart_services(
            self,
            service_names: List[str],
            serial_number: str,
    ) -> APIResponse[Optional[ServiceOperationResponse]]:
        """
        调用 controllersrv 重启服务 / Call controllersrv to restart services
        """

        payload = {"service_names": service_names, "serial_number": serial_number}
        response = await self._make_request(
            http.HTTPMethod.POST,
            "/service/restart",
            json_data=payload,
            response_models=self.SERVICE_OPERATION_MODELS,
        )
        return cast(APIResponse[Optional[ServiceOperationResponse]], response)

    async def start_services(
            self,
            service_names: List[str],
            serial_number: str,
    ) -> APIResponse[Optional[ServiceOperationResponse]]:
        """
        调用 controllersrv 启动服务 / Call controllersrv to start services
        """

        payload = {"service_names": service_names, "serial_number": serial_number}
        response = await self._make_request(
            http.HTTPMethod.POST,
            "/service/start",
            json_data=payload,
            response_models=self.SERVICE_OPERATION_MODELS,
        )
        return cast(APIResponse[Optional[ServiceOperationResponse]], response)

    async def stop_services(
            self,
            service_names: List[str],
            serial_number: str,
    ) -> APIResponse[Optional[ServiceOperationResponse]]:
        """
        调用 controllersrv 停止服务 / Call controllersrv to stop services
        """
        logger.info(f"Stopping services: {service_names} with serial number: {serial_number}")
        payload = {"service_names": service_names, "serial_number": serial_number}
        response = await self._make_request(
            http.HTTPMethod.POST,
            "/service/stop",
            json_data=payload,
            response_models=self.SERVICE_OPERATION_MODELS,
        )
        return cast(APIResponse[Optional[ServiceOperationResponse]], response)

    async def get_operation_status(
            self,
            serial_number: str,
    ) -> APIResponse[Optional[TaskStatusResponse]]:
        """
        查询异步操作状态 / Query asynchronous operation status
        """

        response = await self._make_request(
            http.HTTPMethod.GET,
            "/task/status",
            params={"serial_number": serial_number},
            response_models=self.TASK_STATUS_MODELS,
        )
        return cast(APIResponse[Optional[TaskStatusResponse]], response)

    async def list_operations(
            self,
            status: Optional[str] = None,
            limit: int = 100,
    ) -> APIResponse[Optional[TaskListResponse]]:
        """
        列出异步操作 / List asynchronous operations
        """

        params: Dict[str, Any] = {}
        if status:
            params["status"] = status
        if limit:
            params["limit"] = limit

        response = await self._make_request(
            http.HTTPMethod.GET,
            "/task/list",
            params=params,
            response_models=self.TASK_LIST_MODELS,
        )
        return cast(APIResponse[Optional[TaskListResponse]], response)
