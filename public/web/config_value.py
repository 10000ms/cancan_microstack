"""配置值扩展 / Config value extension.

提供一个轻量的配置值壳类与解析器：
- 业务配置可直接写具体值（Linglong 原方式）
- 也可写 ConfigValue 壳对象以声明目标类型/反序列化逻辑

Provide a lightweight config wrapper and resolver:
- Keep plain-value config style (Linglong default)
- Support ConfigValue wrapper for typed conversion and custom deserialization
"""
from dataclasses import dataclass
from typing import (
    Any,
    Callable,
    Dict,
)

import orjson
from pydantic import (
    TypeAdapter,
    ValidationError,
)


@dataclass(frozen=True)
class ConfigValue:
    """配置项壳对象 / Typed config wrapper."""

    default: Any
    value_type: Any
    deserializer: Callable[[str], Any] | None = None

    def __init__(
        self,
        default: Any,
        value_type: Any | None = None,
        deserializer: Callable[[str], Any] | None = None,
    ) -> None:
        resolved_type = value_type if value_type is not None else type(default)
        object.__setattr__(self, "default", default)
        object.__setattr__(self, "value_type", resolved_type)
        object.__setattr__(self, "deserializer", deserializer)

    def parse(self, raw_value: Any) -> Any:
        """将远程配置值解析为声明类型 / Parse remote value into declared type."""
        if self.deserializer:
            if isinstance(raw_value, str):
                return self.deserializer(raw_value)
            return self.deserializer(str(raw_value))

        adapter = TypeAdapter(self.value_type)

        if isinstance(raw_value, str):
            if self.value_type is str:
                return adapter.validate_python(raw_value)
            try:
                return adapter.validate_json(raw_value)
            except ValidationError:
                return adapter.validate_python(raw_value)

        return adapter.validate_python(raw_value)


class ConfigValueResolver:
    """配置值解析器 / Resolver for plain config values and ConfigValue wrappers."""

    def __init__(self, wrappers: Dict[str, ConfigValue] | None = None) -> None:
        self._wrappers = wrappers or {}

    @classmethod
    def from_snapshot(cls, config_snapshot: Dict[str, Any]) -> "ConfigValueResolver":
        wrappers: Dict[str, ConfigValue] = {}
        for key, value in config_snapshot.items():
            if isinstance(value, ConfigValue):
                wrappers[key] = value
        return cls(wrappers=wrappers)

    def get_wrapper(self, config_key: str) -> ConfigValue | None:
        return self._wrappers.get(config_key)

    def materialize_defaults(self) -> Dict[str, Any]:
        """提取壳对象默认值用于运行态配置 / Materialize wrapper defaults for runtime config."""
        return {
            key: wrapper.default
            for key, wrapper in self._wrappers.items()
        }

    def resolve_update_value(self, config_key: str, current_value: Any, raw_value: Any) -> Any:
        """解析更新值 / Resolve updated value by key type strategy."""
        wrapper = self.get_wrapper(config_key)
        if wrapper is not None:
            return wrapper.parse(raw_value)

        # Linglong 默认兼容策略：
        # 非字符串配置项接收字符串时，先尝试 JSON 反序列化；失败则原样字符串赋值。
        # Linglong-compatible behavior:
        # For non-str config receiving str input, try JSON deserialize first;
        # fallback to raw string on failure.
        if isinstance(raw_value, str) and not isinstance(current_value, str):
            try:
                return orjson.loads(raw_value)
            except orjson.JSONDecodeError:
                return raw_value

        return raw_value
