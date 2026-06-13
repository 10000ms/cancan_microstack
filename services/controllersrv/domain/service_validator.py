"""
服务验证模块

负责验证服务名称是否合法、是否可操作
"""
import yaml
from typing import (
    List,
    Set,
    Optional,
    Dict,
    Any,
)
from pathlib import Path
from linglong_web.utils import logger
from cancan_microstack.public.const.controllersrv_consts import (
    ServiceCategory,
    INFRASTRUCTURE_SERVICES,
    FRAMEWORK_SERVICES,
    ValidationResultKey,
)
from dragonfly_container.core import UnifiedExecutor


class ServiceValidator:
    """
    服务验证器
    
    职责：
    1. 从 docker-compose.yml 读取所有服务定义
    2. 区分基础设施服务、框架服务、业务服务
    3. 验证服务名称是否合法、是否可操作
    
    使用 Dragonfly Container 的 UnifiedExecutor 来获取服务信息
    """

    def __init__(self, compose_file: str, executor: Optional[UnifiedExecutor] = None):
        """
        初始化验证器
        
        Args:
            compose_file: docker-compose.yml 文件路径
            executor: Dragonfly Container UnifiedExecutor 实例（可选，用于获取动态服务信息）
        """
        self.compose_file = compose_file
        self.executor = executor
        self._all_services: Set[str] = set()
        self._operable_services: Set[str] = set()
        self._service_category_map: Dict[str, ServiceCategory] = {}

        # 加载服务定义
        self._load_services()

    def _load_services(self):
        """
        从 docker-compose.yml 加载服务定义
        
        使用 Dragonfly Container 的 UnifiedExecutor 获取配置（如果可用），
        否则直接解析 YAML 文件
        """
        try:
            compose_path = Path(self.compose_file)
            if not compose_path.exists():
                logger.error(f"Docker Compose file not found: {self.compose_file}")
                return

            # 优先使用 executor 获取配置（如果可用）
            if self.executor:
                services = self._get_services_from_executor()
            else:
                services = None

            # 如果 executor 不可用或获取失败，回退到直接读取 YAML
            if not services:
                logger.info("Using direct YAML parse to get services")
                services = self._get_services_from_yaml()

            self._all_services = set(services.keys())

            # 分类服务
            for service_name in self._all_services:
                category = self._categorize_service(service_name)
                self._service_category_map[service_name] = category

                # 只有业务服务可操作
                if category == ServiceCategory.BUSINESS:
                    self._operable_services.add(service_name)

            logger.info(
                f"Loaded services from compose file: "
                f"total={len(self._all_services)}, "
                f"operable={len(self._operable_services)}"
            )
            logger.info(f"Operable services: {sorted(self._operable_services)}")

        except Exception as e:
            logger.error(f"Failed to load services from compose file: {e}", exc_info=True)

    def _get_services_from_executor(self) -> Dict[str, Any]:
        """
        使用 Dragonfly Container UnifiedExecutor 获取服务列表
        
        使用 executor 的 build_config_command 方法构建命令，然后执行
        
        Returns:
            服务字典，失败返回空字典
        """
        import subprocess

        try:
            if not self.executor:
                return {}

            # 使用 executor 构建 config 命令
            cmd = self.executor.compose.build_config_command()
            logger.debug(f"Getting services using executor: {' '.join(cmd)}")

            compose_path = Path(self.compose_file)
            work_dir = compose_path.parent

            result = subprocess.run(
                cmd,
                cwd=work_dir,
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode != 0:
                logger.warning(f"Compose config command failed: {result.stderr}")
                return {}

            # 解析输出的 YAML
            config_data = yaml.safe_load(result.stdout)
            services = config_data.get('services', {})
            logger.debug(f"Got {len(services)} services from executor")
            return services

        except subprocess.TimeoutExpired:
            logger.warning("Compose config command timeout")
            return {}
        except Exception as e:
            logger.debug(f"Failed to get services from executor: {e}")
            return {}

    def _get_services_from_yaml(self) -> Dict[str, Any]:
        """
        直接从 YAML 文件读取服务（回退方案）
        
        Returns:
            服务字典
        """
        with open(self.compose_file, 'r', encoding='utf-8') as f:
            compose_data = yaml.safe_load(f)

        return compose_data.get('services', {})

    def _categorize_service(self, service_name: str) -> ServiceCategory:
        """
        对服务进行分类
        
        Args:
            service_name: 服务名称
        
        Returns:
            服务分类
        """
        # 标准化服务名称（去掉 .service 后缀）
        base_name = service_name.replace('.service', '')
        full_name = f"{base_name}.service"

        # 检查是否是基础设施服务
        if base_name in INFRASTRUCTURE_SERVICES or full_name in INFRASTRUCTURE_SERVICES:
            return ServiceCategory.INFRASTRUCTURE

        # 检查是否是框架服务
        if base_name in FRAMEWORK_SERVICES or full_name in FRAMEWORK_SERVICES:
            return ServiceCategory.FRAMEWORK

        # 其他都是业务服务
        return ServiceCategory.BUSINESS

    def is_valid_service(self, service_name: str) -> bool:
        """
        检查服务名称是否在 docker-compose.yml 中定义
        
        Args:
            service_name: 服务名称
        
        Returns:
            是否有效
        """
        # 标准化服务名称
        base_name = service_name.replace('.service', '')
        full_name = f"{base_name}.service"

        return service_name in self._all_services or \
            base_name in self._all_services or \
            full_name in self._all_services

    def is_operable_service(self, service_name: str) -> bool:
        """
        检查服务是否可操作（仅业务服务可操作）
        
        Args:
            service_name: 服务名称
        
        Returns:
            是否可操作
        """
        # 标准化服务名称
        base_name = service_name.replace('.service', '')
        full_name = f"{base_name}.service"

        return service_name in self._operable_services or \
            base_name in self._operable_services or \
            full_name in self._operable_services

    def get_service_category(self, service_name: str) -> Optional[ServiceCategory]:
        """
        获取服务分类
        
        Args:
            service_name: 服务名称
        
        Returns:
            服务分类，不存在返回 None
        """
        # 标准化服务名称
        base_name = service_name.replace('.service', '')
        full_name = f"{base_name}.service"

        return self._service_category_map.get(service_name) or \
            self._service_category_map.get(base_name) or \
            self._service_category_map.get(full_name)

    def validate_service_names(self, service_names: List[str]) -> Dict[str, Any]:
        """
        批量验证服务名称
        
        Args:
            service_names: 服务名称列表
        
        Returns:
            验证结果字典：
            {
                "valid": bool,
                "invalid_services": [],
                "non_operable_services": [],
                "valid_services": []
            }
        """
        invalid_services = []
        non_operable_services = []
        valid_services = []

        for service_name in service_names:
            # 检查是否存在
            if not self.is_valid_service(service_name):
                invalid_services.append(service_name)
                continue

            # 检查是否可操作
            if not self.is_operable_service(service_name):
                non_operable_services.append(service_name)
                continue

            valid_services.append(service_name)

        return {
            ValidationResultKey.VALID: len(invalid_services) == 0 and len(non_operable_services) == 0,
            ValidationResultKey.INVALID_SERVICES: invalid_services,
            ValidationResultKey.NON_OPERABLE_SERVICES: non_operable_services,
            ValidationResultKey.VALID_SERVICES: valid_services,
        }

    def get_all_services(self) -> List[str]:
        """获取所有服务列表"""
        return sorted(self._all_services)

    def get_operable_services(self) -> List[str]:
        """获取所有可操作的服务列表"""
        return sorted(self._operable_services)

    def get_services_by_category(self, category: ServiceCategory) -> List[str]:
        """
        按分类获取服务列表
        
        Args:
            category: 服务分类
        
        Returns:
            服务名称列表
        """
        return sorted([
            name for name, cat in self._service_category_map.items()
            if cat == category
        ])


# 全局验证器实例
_global_validator: Optional[ServiceValidator] = None


def get_service_validator() -> Optional[ServiceValidator]:
    """获取全局服务验证器实例"""
    return _global_validator


def init_service_validator(compose_file: str, executor: Optional[UnifiedExecutor] = None):
    """
    初始化全局服务验证器
    
    Args:
        compose_file: docker-compose.yml 文件路径
        executor: Dragonfly Container UnifiedExecutor 实例（可选）
    """
    global _global_validator
    _global_validator = ServiceValidator(compose_file, executor)
    logger.info("Global service validator initialized")


def reset_service_validator():
    """重置全局服务验证器（主要用于测试）"""
    global _global_validator
    _global_validator = None
    logger.info("Global service validator reset")
