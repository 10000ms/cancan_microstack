import sys
from pathlib import Path


def _ensure_project_paths() -> None:
    """动态注入项目路径，避免 ImportError / Inject project paths dynamically to avoid import errors"""

    project_root = Path(__file__).resolve().parent.parent.parent.parent.parent
    extra_paths = [
        project_root / "src",
        project_root / "src" / "libs",
        project_root / "cmd",
    ]

    for path in extra_paths:
        path_str = str(path)
        if path_str not in sys.path:
            sys.path.insert(0, path_str)


_ensure_project_paths()

from cancan_microstack.public.web.config_value import (
    ConfigValue,
    ConfigValueResolver,
)


def test_config_value_parse_int_from_string() -> None:
    wrapper = ConfigValue(default=0, value_type=int)

    value = wrapper.parse("1")

    assert value == 1
    assert isinstance(value, int)


def test_config_value_parse_str_from_string() -> None:
    wrapper = ConfigValue(default="default", value_type=str)

    value = wrapper.parse("1")

    assert value == "1"
    assert isinstance(value, str)


def test_config_value_parse_dict_from_json_string() -> None:
    wrapper = ConfigValue(default={"a": 0}, value_type=dict[str, int])

    value = wrapper.parse('{"a": 1}')

    assert value == {"a": 1}


def test_resolver_discovers_wrappers_and_materializes_defaults() -> None:
    snapshot = {
        "INT_KEY": ConfigValue(default=2, value_type=int),
        "STR_KEY": ConfigValue(default="x", value_type=str),
        "PLAIN_KEY": "plain",
    }

    resolver = ConfigValueResolver.from_snapshot(snapshot)
    defaults = resolver.materialize_defaults()

    assert sorted(defaults.keys()) == ["INT_KEY", "STR_KEY"]
    assert defaults["INT_KEY"] == 2
    assert defaults["STR_KEY"] == "x"


def test_resolver_plain_value_falls_back_to_raw_string_on_json_failure() -> None:
    resolver = ConfigValueResolver()

    value = resolver.resolve_update_value(
        config_key="ANY_KEY",
        current_value=0,
        raw_value="not-json",
    )

    assert value == "not-json"
