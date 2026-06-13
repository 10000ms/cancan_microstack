"""Cancan microstack service entrypoints under cmd/.

该目录用于放置 cancan_microstack 内置服务启动入口（controllersrv/infrasrv/opsbffsrv）。
This directory hosts builtin service entrypoints (controllersrv/infrasrv/opsbffsrv).

⚠️ 注意 / Note:
Python 标准库也有一个名为 `cmd` 的模块，pytest/pdb 会依赖其中的 `Cmd`。
当开发者在源码目录下运行（例如直接在 cancan_microstack 仓库根目录执行 pytest）时，
同名目录 `cmd/` 会遮蔽标准库模块，导致 pytest 在启动阶段崩溃。

为保证：
- 仍保留 `cancan_microstack.cmd.*` 入口结构 / keep entrypoints importable
- 同时 `import cmd; cmd.Cmd` 仍指向标准库实现 / keep stdlib cmd symbols available

这里做一个轻量桥接：从标准库路径加载 `cmd.py` 并暴露必要符号。
"""
import importlib.util
import sysconfig
from pathlib import Path
from types import ModuleType


def _load_stdlib_cmd_module() -> ModuleType:
	"""加载标准库 cmd 模块（避免被当前包遮蔽）。
	Load stdlib cmd module without being shadowed by this package.
	"""

	stdlib_dir = sysconfig.get_path("stdlib")
	if not stdlib_dir:
		raise RuntimeError("Unable to locate stdlib path / 无法定位标准库路径")

	cmd_py_path = Path(stdlib_dir) / "cmd.py"
	if not cmd_py_path.exists():
		raise RuntimeError(f"Stdlib cmd.py not found at: {cmd_py_path}")

	spec = importlib.util.spec_from_file_location("_stdlib_cmd", cmd_py_path)
	if spec is None or spec.loader is None:
		raise RuntimeError("Unable to load stdlib cmd spec / 无法加载标准库 cmd 模块 spec")

	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	return module


_stdlib_cmd = _load_stdlib_cmd_module()

# Expose stdlib symbols used by pdb/pytest.
# 暴露 pdb/pytest 依赖的标准库符号。
Cmd = _stdlib_cmd.Cmd  # type: ignore[attr-defined]

__all__ = [
	"Cmd",
]

