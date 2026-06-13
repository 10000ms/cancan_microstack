"""
容器环境检测工具。
Container environment detection utilities.

自动检测当前环境使用的是 Docker 还是 Podman，并提供统一的命令接口。
Automatically detect whether the runtime uses Docker or Podman and expose unified compose helpers.
"""

import shutil
import subprocess
from typing import Optional

from linglong_web.utils import logger


class ContainerEnv:
    """
    容器环境管理器。
    Container environment manager responsible for lazy detection and caching results.
    """

    _detected_engine: Optional[str] = None
    _detected_compose_cmd: Optional[str] = None

    @classmethod
    def detect_engine(cls) -> str:
        """
        检测容器引擎类型。
        Detect container engine type and cache the decision.

        Returns:
            "podman" 或 "docker" / either "podman" or "docker".
        """

        if cls._detected_engine:
            return cls._detected_engine

        # 优先检测 Podman / prefer Podman first for local dev parity
        if shutil.which("podman"):
            try:
                result = subprocess.run(
                    ["podman", "--version"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    check=False,
                )
                if result.returncode == 0:
                    logger.info("Detected Podman: %s", result.stdout.strip())
                    cls._detected_engine = "podman"
                    return "podman"
            except Exception as exc:  # noqa: BLE001 - log unexpected detection errors
                logger.warning("Failed to verify podman: %s", exc)

        # 其次检测 Docker / fallback to Docker detection
        if shutil.which("docker"):
            try:
                result = subprocess.run(
                    ["docker", "--version"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    check=False,
                )
                if result.returncode == 0:
                    logger.info("Detected Docker: %s", result.stdout.strip())
                    cls._detected_engine = "docker"
                    return "docker"
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to verify docker: %s", exc)

        # 默认返回 docker / Default to docker
        logger.warning("No container engine detected, defaulting to docker")
        cls._detected_engine = "docker"
        return "docker"

    @classmethod
    def detect_compose_command(cls) -> str:
        """
        检测 Compose 命令。
        Detect compose command (docker compose, docker-compose, podman compose, etc.).

        Returns:
            完整命令字符串 / composed command name string.
        """

        if cls._detected_compose_cmd:
            return cls._detected_compose_cmd

        engine = cls.detect_engine()

        if engine == "podman":
            # Podman 环境：优先 podman-compose，其次 podman compose
            if shutil.which("podman-compose"):
                try:
                    result = subprocess.run(
                        ["podman-compose", "--version"],
                        capture_output=True,
                        text=True,
                        timeout=5,
                        check=False,
                    )
                    if result.returncode == 0:
                        logger.info("Using podman-compose: %s", result.stdout.strip())
                        cls._detected_compose_cmd = "podman-compose"
                        return "podman-compose"
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Failed to verify podman-compose: %s", exc)

            # 尝试 podman compose（Podman 4.0+ 内置）
            try:
                result = subprocess.run(
                    ["podman", "compose", "version"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    check=False,
                )
                if result.returncode == 0:
                    logger.info("Using podman compose: %s", result.stdout.strip())
                    cls._detected_compose_cmd = "podman compose"
                    return "podman compose"
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to verify podman compose: %s", exc)
        else:
            # Docker 环境：优先 docker compose（v2），其次 docker-compose（v1）
            try:
                result = subprocess.run(
                    ["docker", "compose", "version"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    check=False,
                )
                if result.returncode == 0:
                    logger.info("Using docker compose: %s", result.stdout.strip())
                    cls._detected_compose_cmd = "docker compose"
                    return "docker compose"
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to verify docker compose: %s", exc)

            if shutil.which("docker-compose"):
                try:
                    result = subprocess.run(
                        ["docker-compose", "--version"],
                        capture_output=True,
                        text=True,
                        timeout=5,
                        check=False,
                    )
                    if result.returncode == 0:
                        logger.info("Using docker-compose: %s", result.stdout.strip())
                        cls._detected_compose_cmd = "docker-compose"
                        return "docker-compose"
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Failed to verify docker-compose: %s", exc)

        logger.warning("No compose command detected, defaulting to docker-compose")
        cls._detected_compose_cmd = "docker-compose"
        return "docker-compose"

    @classmethod
    def get_compose_command_list(cls, compose_file: str, project_name: str) -> list[str]:
        """
        获取 compose 命令的基础命令列表。
        Build the command list for executing compose operations.

        Args:
            compose_file: compose 文件路径 / compose file path.
            project_name: 项目名称 / compose project name.

        Returns:
            命令列表，如 ["podman-compose", "-f", "xxx.yml", "-p", "project"]。
        """

        compose_cmd = cls.detect_compose_command()
        cmd_parts = compose_cmd.split()
        return cmd_parts + ["-f", compose_file, "-p", project_name]

    @classmethod
    def get_info(cls) -> dict[str, str | bool]:
        """
        获取容器环境信息。
        Return a summary dict of the detected container environment.
        """

        engine = cls.detect_engine()
        compose_cmd = cls.detect_compose_command()
        return {
            "engine": engine,
            "compose_command": compose_cmd,
            "is_podman": engine == "podman",
            "is_docker": engine == "docker",
        }


def get_container_engine() -> str:
    """获取容器引擎类型 / Expose detected container engine."""

    return ContainerEnv.detect_engine()


def get_compose_command() -> str:
    """获取 compose 命令 / Expose detected compose command."""

    return ContainerEnv.detect_compose_command()


def is_podman_env() -> bool:
    """判断是否为 Podman 环境 / Return True when Podman is available."""

    return ContainerEnv.detect_engine() == "podman"


def is_docker_env() -> bool:
    """判断是否为 Docker 环境 / Return True when Docker is available."""

    return ContainerEnv.detect_engine() == "docker"
