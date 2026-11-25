"""Entry point for ``python -m accepttwin`` (P032 T012).

Thin wrapper only: all logic lives in :mod:`accepttwin.cli`.
"""

from __future__ import annotations

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
