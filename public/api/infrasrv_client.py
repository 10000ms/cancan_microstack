"""InfraSrv API 客户端基类 / InfraSrv API client base class."""
import http
from typing import (
    Any,
    Dict,
    Optional,
    Sequence,
    Tuple,
    Type,
    cast,
)

from pydantic import (
    BaseModel,
    ValidationError,
)

from linglong_web.utils import logger
from linglong_web import http_client, HTTPClientConfig
from cancan_microstack.public.schemas.common import (
    APIError,
    APIResponse,
)
from cancan_microstack.public.schemas.infra.operation import (
    OperationCreateRequest,
    OperationUpdateRequest,
    OperationResponse,
    OperationListResponse,
)


class InfraSrvApiClient:
    """InfraSrv API 客户端基类 / TableBase client for InfraSrv APIs."""

    OPERATION_RESPONSE_MODELS: Tuple[Type[BaseModel], ...] = (OperationResponse,)
    OPERATION_LIST_MODELS: Tuple[Type[BaseModel], ...] = (OperationListResponse,)

    def __init__(self, base_url: str):
        """
        初始化 API 客户端 / Initialise API client
        
        Args:
            base_url: infrasrv 的基础 URL / TableBase URL for infrasrv
        """

        self.base_url = base_url
        logger.info(f"InfraSrvApiClient initialized with base_url: {self.base_url}")

    async def _make_request(
            self,
            method: http.HTTPMethod,
            endpoint: str,
            json_data: Optional[Dict[str, Any]] = None,
            params: Optional[Dict[str, Any]] = None,
            response_models: Sequence[Type[BaseModel]] = (),
    ) -> APIResponse[Any]:
        """
        通用请求方法 / Generic request executor
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
            logger.error(f"Error calling infrasrv API [{endpoint}]: {exc}", exc_info=True)
            return APIResponse(success=False, error=APIError(code="HTTP_EXCEPTION", msg=str(exc)))

        if response is None:
            logger.error(f"Failed to call infrasrv API [{endpoint}]: no response")
            return APIResponse(success=False, error=APIError(code="HTTP_NO_RESPONSE", msg="No response received"))

        if response.status != 200:
            error_message = f"HTTP error: {response.status}"
            logger.error(f"infrasrv API [{endpoint}] returned non-200 status: {response.status}")
            return APIResponse(success=False, error=APIError(code=str(response.status), msg=error_message))

        try:
            payload = await response.json()
        except Exception as exc:
            logger.error(f"Failed to decode infrasrv response for [{endpoint}]: {exc}", exc_info=True)
            return APIResponse(success=False, error=APIError(code="JSON_DECODE_ERROR", msg=str(exc)))

        if not isinstance(payload, dict):
            logger.error(f"Unexpected infrasrv response format for [{endpoint}]: {payload}")
            return APIResponse(success=False, error=APIError(code="INVALID_PAYLOAD", msg="Response is not a dict"))

        success = bool(payload.get("success"))
        error_payload = payload.get("error") or {}
        api_error = self._create_api_error(error_payload)
        raw_data = payload.get("data")
        parsed_data = self._parse_response_data(raw_data, response_models)

        if parsed_data is None and raw_data is not None and response_models:
            logger.error(
                "Failed to parse infrasrv response data for [%s]: %s",
                endpoint,
                raw_data,
            )

        logger.debug(
            "infrasrv API [%s] completed: success=%s, code=%s",
            endpoint,
            success,
            api_error.code,
        )

        return APIResponse(success=success, error=api_error, data=parsed_data)

    @staticmethod
    def _create_api_error(error_payload: Any) -> APIError:
        """构造 APIError / Build APIError"""

        if isinstance(error_payload, dict):
            code = str(error_payload.get("code", "50000"))
            msg = str(error_payload.get("msg", ""))
        else:
            code = "50000"
            msg = str(error_payload) if error_payload is not None else ""
        return APIError(code=code, msg=msg)

    def _parse_response_data(
            self,
            data: Any,
            response_models: Sequence[Type[BaseModel]],
    ) -> Any:
        """
        解析响应数据为 Pydantic 模型 / Parse response data into Pydantic models
        如果 response_models 为空，则直接返回原始数据 / If response_models is empty, return raw data
        """

        if data is None:
            return None

        if not response_models:
            return data

        if not isinstance(data, (dict, list)):
            return None

        for model in response_models:
            try:
                if isinstance(data, model):
                    return data
                return model.model_validate(data)
            except ValidationError:
                continue

        return None

    async def create_operation(self, request: OperationCreateRequest) -> APIResponse[Optional[OperationResponse]]:
        """创建操作记录 / Create operation record"""

        json_data = request.model_dump(mode="json")
        response = await self._make_request(
            http.HTTPMethod.POST,
            "/operation/create",
            json_data=json_data,
            response_models=self.OPERATION_RESPONSE_MODELS,
        )
        return cast(APIResponse[Optional[OperationResponse]], response)

    async def update_operation(self, request: OperationUpdateRequest) -> APIResponse[Optional[OperationResponse]]:
        """更新操作记录 / Update operation record"""

        json_data = request.model_dump(mode="json", exclude_none=True)
        if request.started_at:
            json_data["started_at"] = request.started_at.isoformat()
        if request.completed_at:
            json_data["completed_at"] = request.completed_at.isoformat()

        response = await self._make_request(
            http.HTTPMethod.POST,
            "/operation/update",
            json_data=json_data,
            response_models=self.OPERATION_RESPONSE_MODELS,
        )
        return cast(APIResponse[Optional[OperationResponse]], response)

    async def get_operation(self, operation_id: str) -> APIResponse[Optional[OperationResponse]]:
        """获取操作记录 / Get operation record"""

        response = await self._make_request(
            http.HTTPMethod.GET,
            "/operation/get",
            params={"operation_id": operation_id},
            response_models=self.OPERATION_RESPONSE_MODELS,
        )
        return cast(APIResponse[Optional[OperationResponse]], response)

    async def list_operations(
            self,
            service_name: Optional[str] = None,
            status: Optional[str] = None,
            limit: int = 50,
            offset: int = 0,
    ) -> APIResponse[Optional[OperationListResponse]]:
        """列出操作记录 / List operation records"""

        params: Dict[str, Any] = {"limit": limit, "offset": offset}
        if service_name:
            params["service_name"] = service_name
        if status:
            params["status"] = status

        response = await self._make_request(
            http.HTTPMethod.GET,
            "/operation/list",
            params=params,
            response_models=self.OPERATION_LIST_MODELS,
        )
        return cast(APIResponse[Optional[OperationListResponse]], response)

    # --- Workflow Methods ---

    async def list_workflow_definitions(
            self,
            page: int = 1,
            page_size: int = 20,
            keyword: Optional[str] = None,
            status: Optional[str] = None,
    ) -> APIResponse[Any]:
        """列出工作流定义 / List workflow definitions with pagination."""

        params: Dict[str, Any] = {
            "page": page,
            "page_size": page_size,
        }
        if keyword:
            params["keyword"] = keyword
        if status:
            params["status"] = status
        return await self._make_request(
            http.HTTPMethod.GET,
            "/v1/infrasrv/workflows",
            params=params,
        )

    async def get_workflow_definition(self, workflow_id: str) -> APIResponse[Any]:
        """获取工作流详情 / Get workflow details"""
        return await self._make_request(
            http.HTTPMethod.GET,
            f"/v1/infrasrv/workflows/{workflow_id}",
        )

    async def get_workflow(self, workflow_id: str) -> APIResponse[Any]:
        """别名 / Alias."""
        return await self.get_workflow_definition(workflow_id)

    async def list_workflow_runs(
            self,
            workflow_id: Optional[str] = None,
            reqid: Optional[str] = None,
            page: int = 1,
            page_size: int = 20,
            status: Optional[str] = None,
            date_from: Optional[str] = None,
            date_to: Optional[str] = None,
    ) -> APIResponse[Any]:
        """列出工作流运行记录 / List workflow runs"""
        params = {"page": page, "page_size": page_size}
        if workflow_id:
            params["workflow_id"] = workflow_id
        if reqid:
            params["reqid"] = reqid
        if status:
            params["status"] = status
        if date_from:
            params["date_from"] = date_from
        if date_to:
            params["date_to"] = date_to
        return await self._make_request(
            http.HTTPMethod.GET,
            "/v1/infrasrv/runs",
            params=params
        )

    async def get_run_graph_status(self, run_id: str) -> APIResponse[Any]:
        """获取运行图状态 / Get run graph status"""
        return await self._make_request(
            http.HTTPMethod.GET,
            f"/v1/infrasrv/runs/{run_id}/status",
            params={}
        )

    async def get_node_history(self, run_id: str, node_id: str) -> APIResponse[Any]:
        """获取节点历史 / Get node history"""
        return await self._make_request(
            http.HTTPMethod.GET,
            f"/v1/infrasrv/runs/{run_id}/nodes/{node_id}/history",
        )

    async def get_workflow_stats(self) -> APIResponse[Any]:
        """获取工作流统计 / Get workflow statistics"""
        return await self._make_request(
            http.HTTPMethod.GET,
            "/v1/infrasrv/workflows/stats",
        )

    async def create_workflow_definition(self, payload: Dict[str, Any]) -> APIResponse[Any]:
        """创建工作流定义 / Create workflow definition"""
        return await self._make_request(
            http.HTTPMethod.POST,
            "/v1/infrasrv/workflows",
            json_data=payload
        )

    async def update_workflow_definition(self, workflow_id: str, payload: Dict[str, Any]) -> APIResponse[Any]:
        """更新工作流定义 / Update workflow definition"""
        return await self._make_request(
            http.HTTPMethod.PUT,
            f"/v1/infrasrv/workflows/{workflow_id}",
            json_data=payload
        )

    async def delete_workflow_definition(self, workflow_id: str) -> APIResponse[Any]:
        """删除工作流定义 / Delete workflow definition"""
        return await self._make_request(
            http.HTTPMethod.DELETE,
            f"/v1/infrasrv/workflows/{workflow_id}"
        )

    async def list_workflow_versions(self, workflow_id: str, limit: int = 50) -> APIResponse[Any]:
        """列出工作流版本历史 / List workflow definition versions"""
        params = {"limit": limit}
        return await self._make_request(
            http.HTTPMethod.GET,
            f"/v1/infrasrv/workflows/{workflow_id}/versions",
            params=params,
        )

    async def rollback_workflow_definition(self, workflow_id: str, payload: Dict[str, Any]) -> APIResponse[Any]:
        """回滚工作流定义 / Roll back workflow definition"""
        return await self._make_request(
            http.HTTPMethod.POST,
            f"/v1/infrasrv/workflows/{workflow_id}/rollback",
            json_data=payload,
        )

    async def trigger_workflow_run(self, workflow_id: str, payload: Dict[str, Any]) -> APIResponse[Any]:
        """触发工作流运行 / Trigger workflow run"""
        return await self._make_request(
            http.HTTPMethod.POST,
            f"/v1/infrasrv/workflows/{workflow_id}/trigger",
            json_data=payload
        )

    async def list_workflow_engine_alerts(
            self,
            *,
            status: Optional[str] = None,
            severity: Optional[str] = None,
            run_id: Optional[str] = None,
            page: int = 1,
            page_size: int = 20,
    ) -> APIResponse[Any]:
        """列出工作流引擎告警 / List workflow engine alerts"""

        params: Dict[str, Any] = {
            "page": page,
            "page_size": page_size,
        }
        if status:
            params["status"] = status
        if severity:
            params["severity"] = severity
        if run_id:
            params["run_id"] = run_id
        return await self._make_request(
            http.HTTPMethod.GET,
            "/v1/infrasrv/workflows/alerts",
            params=params,
        )

    async def acknowledge_workflow_engine_alert(
            self,
            alert_id: str,
            payload: Dict[str, Any],
    ) -> APIResponse[Any]:
        """标记告警为已知晓 / Acknowledge workflow engine alert"""

        return await self._make_request(
            http.HTTPMethod.POST,
            f"/v1/infrasrv/workflows/alerts/{alert_id}/ack",
            json_data=payload,
        )

    async def resolve_workflow_engine_alert(
            self,
            alert_id: str,
            payload: Dict[str, Any],
    ) -> APIResponse[Any]:
        """标记告警为已解决 / Resolve workflow engine alert"""

        return await self._make_request(
            http.HTTPMethod.POST,
            f"/v1/infrasrv/workflows/alerts/{alert_id}/resolve",
            json_data=payload,
        )
