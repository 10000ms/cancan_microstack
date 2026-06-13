"""`cancan doctor` — pre-flight environment & configuration checks.

在 `cancan stack up` 之前一次性诊断常见的"起不来"原因：容器引擎、端口占用、
工作区识别、运行时资产是否就绪、生产弱默认值。

Diagnose the common "stack won't come up" causes before `cancan stack up`:
container engine, port conflicts, workspace detection, bootstrapped runtime
assets, and weak production defaults. Stdlib-only.
"""
from __future__ import annotations

import socket
from dataclasses import dataclass
from pathlib import Path

from ..runtime.compose_cmd import detect_compose_command
from ..runtime.workspace import detect_workspace_root

OK = "ok"
WARN = "warn"
FAIL = "fail"

_GLYPH = {OK: "✓", WARN: "!", FAIL: "✗"}

# Host-published ports declared in the bundled infra compose.
_HOST_PORTS = {
    8080: "caddy (local dev gateway)",
    22100: "controllersrv (host daemon)",
    25432: "postgres",
    26379: "redis",
    27017: "mongo",
    35672: "rabbitmq amqp",
    35673: "rabbitmq management",
}

# Weak local-dev defaults that must not survive into production.
_WEAK_DEFAULTS = {
    "POSTGRES_PASSWORD": "postgres123",
    "RABBITMQ_PASSWORD": "admin123",
    "MONGO_INITDB_ROOT_PASSWORD": "admin123",
    "MONGO_EXPRESS_PASSWORD": "admin123",
    "RABBITMQ_MGMT_PASSWORD": "admin123",
}


@dataclass
class Check:
    status: str
    title: str
    detail: str = ""


def _port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.3)
        return sock.connect_ex((host, port)) == 0


def _parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    try:
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            values[k.strip()] = v.strip()
    except OSError:
        pass
    return values


def collect_checks(workspace: Path) -> list[Check]:
    checks: list[Check] = []

    # 1) container engine + daemon
    try:
        cmd = detect_compose_command()
        checks.append(Check(OK, "Container engine", " ".join(cmd.argv_prefix)))
    except Exception as exc:
        checks.append(Check(FAIL, "Container engine", f"no usable docker/podman compose: {exc}"))

    # 2) host port availability
    busy = [f"{p} ({_HOST_PORTS[p]})" for p in sorted(_HOST_PORTS) if _port_in_use(p)]
    if busy:
        checks.append(Check(WARN, "Host ports", "in use (a previous stack? other apps?): " + ", ".join(busy)))
    else:
        checks.append(Check(OK, "Host ports", "all stack ports free"))

    # 3) workspace detection
    try:
        root = detect_workspace_root(start=workspace)
        checks.append(Check(OK, "Workspace root", str(root)))
    except Exception:
        checks.append(Check(WARN, "Workspace root", f"no workspace marker found under {workspace}; run `cancan init`"))

    # 4) bootstrapped runtime assets
    expected = {
        ".env": workspace / ".env",
        "ddl/create_db.sql": workspace / "ddl" / "create_db.sql",
        "builds/caddy": workspace / "builds" / "caddy",
        "builds/service/Dockerfile": workspace / "builds" / "service" / "Dockerfile",
    }
    missing = [name for name, p in expected.items() if not p.exists()]
    if missing:
        checks.append(Check(WARN, "Runtime assets", "missing (run `cancan stack up --bootstrap` or `cancan init`): " + ", ".join(missing)))
    else:
        checks.append(Check(OK, "Runtime assets", "bootstrapped"))

    # 5) weak defaults / required secrets in .env
    env_path = workspace / ".env"
    if env_path.exists():
        env = _parse_env_file(env_path)
        weak = [k for k, default in _WEAK_DEFAULTS.items() if env.get(k, default) == default]
        if not env.get("AUTH_TOTP_FERNET_KEY"):
            checks.append(Check(FAIL, "AUTH_TOTP_FERNET_KEY", "empty in .env — opsbffsrv will refuse to start in prod mode"))
        else:
            checks.append(Check(OK, "AUTH_TOTP_FERNET_KEY", "set"))
        if weak:
            checks.append(Check(WARN, "Weak default secrets", "still default (CHANGE FOR PRODUCTION): " + ", ".join(weak)))
        else:
            checks.append(Check(OK, "Secrets", "no known weak defaults in .env"))
    else:
        checks.append(Check(WARN, "Config (.env)", "not found; `cancan init` / `stack up --bootstrap` will create it"))

    return checks


def run_doctor(workspace: Path) -> int:
    """运行诊断并打印结果，返回退出码（有 FAIL=2，仅 WARN=0）。
    Run checks, print a report, return an exit code (FAIL → 2, otherwise 0).
    """

    checks = collect_checks(workspace)
    print("cancan doctor — environment check\n")
    for c in checks:
        line = f"  [{_GLYPH[c.status]}] {c.title}"
        if c.detail:
            line += f": {c.detail}"
        print(line)

    fails = sum(1 for c in checks if c.status == FAIL)
    warns = sum(1 for c in checks if c.status == WARN)
    print()
    if fails:
        print(f"✗ {fails} blocking issue(s), {warns} warning(s). Fix the ✗ items before `cancan stack up`.")
        return 2
    if warns:
        print(f"! {warns} warning(s). The stack can start, but review the ! items (especially before production).")
        return 0
    print("✓ All checks passed.")
    return 0
