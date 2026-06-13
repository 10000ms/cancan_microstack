"""cancan CLI module (library-owned).

说明 / Notes:
- 该目录属于 cancan_microstack（libs），用于提供宿主机侧的 CLI 能力。
  This folder belongs to cancan_microstack (libs) and provides host-side CLI utilities.

- 使用方仓库（consumer repo）不应长期保存框架 CLI 代码；应通过安装 libs 包或
  使用 `python -m cancan_microstack.cmd.cancan.run` 调用。
  Consumer repos should not permanently carry framework CLI code; use the installed package
  or `python -m cancan_microstack.cmd.cancan.run`.
"""
__all__ = []
