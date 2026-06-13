import sys
from pathlib import Path

import pytest


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

from cancan_microstack.public.web.server import AppServer
from cancan_microstack.public.web.config_value import ConfigValue
from linglong_web import LinglongConfig


@pytest.fixture(autouse=True)
def restore_config_snapshot():
    """确保测试结束后还原全局配置 / Restore LinglongConfig snapshot after each test."""

    snapshot = LinglongConfig.snapshot()
    yield
    LinglongConfig.load_from_dict(snapshot)


def _make_server(service_name: str) -> AppServer:
    server = AppServer()
    server.service_name = service_name
    return server


def test_controller_service_always_skips_registry():
    server = _make_server("controllersrv")
    LinglongConfig.SKIP_SERVICE_REGISTRY = False
    LinglongConfig.IS_CONTROLLER_SERVICE = True

    assert server._should_skip_registry() is True


def test_explicit_config_can_skip_regular_service():
    server = _make_server("besrv")
    LinglongConfig.SKIP_SERVICE_REGISTRY = True
    LinglongConfig.IS_CONTROLLER_SERVICE = False

    assert server._should_skip_registry() is True


def test_regular_service_registers_when_no_policy_applies():
    server = _make_server("besrv")
    LinglongConfig.SKIP_SERVICE_REGISTRY = False
    LinglongConfig.IS_CONTROLLER_SERVICE = False

    assert server._should_skip_registry() is False


def test_initialize_config_value_resolver_materializes_default_value():
    server = _make_server("besrv")
    LinglongConfig.TYPED_DEMO = ConfigValue(default=7, value_type=int)

    server._initialize_config_value_resolver()

    assert LinglongConfig.TYPED_DEMO == 7


def test_update_config_with_config_value_wrapper_parses_typed_value():
    server = _make_server("besrv")
    LinglongConfig.TYPED_DEMO = ConfigValue(default=1, value_type=int)
    server._initialize_config_value_resolver()

    server._update_config({"typed_demo": "2"})

    assert LinglongConfig.TYPED_DEMO == 2
    assert isinstance(LinglongConfig.TYPED_DEMO, int)


def test_update_config_plain_value_falls_back_to_string_when_json_invalid():
    server = _make_server("besrv")
    LinglongConfig.PLAIN_DEMO = 0
    server._initialize_config_value_resolver()

    server._update_config({"plain_demo": "abc"})

    assert LinglongConfig.PLAIN_DEMO == "abc"


def test_update_config_plain_value_parses_json_when_possible():
    server = _make_server("besrv")
    LinglongConfig.PLAIN_DEMO = 0
    server._initialize_config_value_resolver()

    server._update_config({"plain_demo": "1"})

    assert LinglongConfig.PLAIN_DEMO == 1
    assert isinstance(LinglongConfig.PLAIN_DEMO, int)
