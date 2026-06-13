import subprocess
from pathlib import Path

import pytest


def test_detect_compose_command_prefers_docker_compose(monkeypatch):
    from cancan_microstack.runtime import compose_cmd

    def fake_which(name: str):
        if name == "docker":
            return "/usr/local/bin/docker"
        return None

    def fake_run(cmd, **kwargs):
        # docker compose version
        if cmd[:2] == ["docker", "compose"] and cmd[2:] == ["version"]:
            return subprocess.CompletedProcess(cmd, 0, "", "")
        return subprocess.CompletedProcess(cmd, 1, "", "")

    cmd = compose_cmd.detect_compose_command(which=fake_which, runner=fake_run)
    assert cmd.argv_prefix == ["docker", "compose"]


def test_detect_compose_command_falls_back_to_podman(monkeypatch):
    from cancan_microstack.runtime import compose_cmd

    def fake_which(name: str):
        if name == "podman":
            return "/usr/local/bin/podman"
        return None

    def fake_run(cmd, **kwargs):
        if cmd[:2] == ["podman", "compose"] and cmd[2:] == ["version"]:
            return subprocess.CompletedProcess(cmd, 0, "", "")
        return subprocess.CompletedProcess(cmd, 1, "", "")

    cmd = compose_cmd.detect_compose_command(which=fake_which, runner=fake_run)
    assert cmd.argv_prefix == ["podman", "compose"]


def test_stack_manager_build_calls_compose_builder(tmp_path: Path):
    from cancan_microstack.core.microstack import CancanMicrostack
    from cancan_microstack.core.stack_manager import StackManager
    from cancan_microstack.core.stack_manager import StackOptions

    stack = CancanMicrostack()
    mgr = StackManager(stack)

    options = StackOptions(
        workspace=tmp_path,
        service_file=None,
        overrides=[],
        output=None,
        bootstrap=False,
        engine=None,
        controllersrv_host="127.0.0.1",
        controllersrv_port=22100,
        with_controllersrv=True,
    )

    compose_file = mgr.build(options)
    assert compose_file.exists()
    assert compose_file.name == "compose.cancan.yml"
