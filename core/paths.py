from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent

if getattr(sys, "frozen", False):
    executable_dir = Path(sys.executable).resolve().parent
    if (executable_dir / "G-Skol.portable").is_file() or (executable_dir / "Col-Div.portable").is_file():
        WORKSPACE = executable_dir / "Workspace"
    else:
        # Installed edition: writable data outside Program Files.
        WORKSPACE = Path(__import__("os").environ.get("SystemDrive", "C:") + "\\G-Skol-Workspace")
else:
    WORKSPACE = ROOT.parent / "Workspace"
