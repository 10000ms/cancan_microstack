"""
controllersrv 验证相关模型

定义服务验证结果等模型
"""
from typing import List

from pydantic import BaseModel


class ValidationResult(BaseModel):
    """服务验证结果模型
    
    Attributes:
        valid: 是否验证通过
        invalid_services: 无效的服务名称列表
        non_operable_services: 不可操作的服务名称列表
        valid_services: 有效的服务名称列表
    """
    valid: bool
    invalid_services: List[str]
    non_operable_services: List[str]
    valid_services: List[str]