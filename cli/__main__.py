"""Entry point so `python -m cancan_microstack.cli` works.

提供 `python -m cancan_microstack.cli` 入口，方便与文档一致。
"""
from .main import main


if __name__ == "__main__":
    raise SystemExit(main())
