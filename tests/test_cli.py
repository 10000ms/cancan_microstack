import importlib
from pathlib import Path

import pytest

cli_main_module = importlib.import_module("cancan_microstack.cli.main")
from cancan_microstack import CancanMicrostack
from cancan_microstack.cli import main as cli_main
from cancan_microstack.core.stack_manager import StackOptions


def test_cli_assets_list(capsys):
    exit_code = cli_main(["assets", "list"])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "docker/docker-compose.infra.yml" in captured.out


def test_cli_compose_build(tmp_path):
    service_file = tmp_path / "docker-compose.services.yml"
    service_file.write_text(
        """
        services:
          another:
            image: demo:latest
        """,
        encoding="utf-8",
    )

    exit_code = cli_main([
        "compose",
        "build",
        "--workspace",
        str(tmp_path),
        "--service-file",
        str(service_file),
    ])

    assert exit_code == 0
    assert (tmp_path / "compose.cancan.yml").exists()


def test_cli_services_run(monkeypatch):
    called = {}

    def fake_run(self, name, host="0.0.0.0", port=8080, workspace=None):
        called["name"] = name
        called["host"] = host
        called["port"] = port
        called["workspace"] = workspace

    monkeypatch.setattr(CancanMicrostack, "run_service", fake_run)
    exit_code = cli_main([
        "services",
        "run",
        "controllersrv",
        "--host",
        "127.0.0.1",
        "--port",
        "9000",
        "--workspace",
        str(Path.cwd()),
    ])

    assert exit_code == 0
    assert called == {
        "name": "controllersrv",
        "host": "127.0.0.1",
        "port": 9000,
        "workspace": Path.cwd(),
    }


def test_cli_controllersrv_restart(monkeypatch, tmp_path):
    events = {"stop": [], "start": [], "wait": []}

    class DummyStackManager:
        def __init__(self, stack):
            self.stack = stack

        def stop_controllersrv(self, workspace):
            events["stop"].append(workspace)
            return True

        def start_controllersrv(self, options):
            events["start"].append(options)
            return 4321

        def wait_controllersrv_ready(self, *, host, port, timeout_seconds):
            events["wait"].append((host, port, timeout_seconds))
            return True

    monkeypatch.setattr(cli_main_module, "StackManager", DummyStackManager)

    exit_code = cli_main([
        "controllersrv",
        "restart",
        "--workspace",
        str(tmp_path),
        "--host",
        "127.0.0.1",
        "--port",
        "23000",
        "--engine",
        "docker",
        "--timeout",
        "5.5",
    ])

    assert exit_code == 0
    assert events["stop"] == [tmp_path]
    assert len(events["start"]) == 1
    start_options = events["start"][0]
    assert isinstance(start_options, StackOptions)
    assert start_options.workspace == tmp_path
    assert start_options.controllersrv_host == "127.0.0.1"
    assert start_options.controllersrv_port == 23000
    assert start_options.engine == "docker"
    assert events["wait"] == [("127.0.0.1", 23000, 5.5)]
