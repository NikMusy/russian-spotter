"""Точка входа для сборки spotter.exe."""

import sys
from pathlib import Path

if not getattr(sys, "frozen", False):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from spotter.__main__ import main

if __name__ == "__main__":
    sys.exit(main())
