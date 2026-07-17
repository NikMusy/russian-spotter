"""Точка входа для сборки recorder.exe."""

import sys
from pathlib import Path

if getattr(sys, "frozen", False):
    ROOT = Path(sys.executable).parent
else:
    ROOT = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(ROOT))

from spotter.recorder_gui import run_recorder

if __name__ == "__main__":
    sys.exit(run_recorder(ROOT))
