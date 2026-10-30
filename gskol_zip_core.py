"""Pack the source Core for sharing without build outputs or local data."""
from __future__ import annotations

import sys
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

EXCLUDE_DIRS = {"build", "dist", "__pycache__", ".git", "Workspace"}
EXCLUDE_SUFFIXES = {".pyc", ".spec"}


def long_path(path: Path) -> Path:
    absolute = str(path.resolve())
    if sys.platform != "win32" or absolute.startswith("\\\\?\\"):
        return Path(absolute)
    if absolute.startswith("\\\\"):
        return Path("\\\\?\\UNC\\" + absolute[2:])
    return Path("\\\\?\\" + absolute)


def main() -> None:
    core = long_path(Path(__file__).parent)
    output = long_path(Path(__file__).parent.parent / "G-Skol-Core-a-envoyer.zip")
    with ZipFile(output, "w", ZIP_DEFLATED, allowZip64=True) as archive:
        for file in core.rglob("*"):
            relative = file.relative_to(core)
            if (not file.is_file() or any(part in EXCLUDE_DIRS for part in relative.parts)
                    or file.suffix.lower() in EXCLUDE_SUFFIXES
                    or file.name.upper().startswith(("JOURNAL", "RESULTAT-BUILD"))):
                continue
            archive.write(file, (Path("Core") / relative).as_posix())
    print(f"ZIP cree : {output}")


if __name__ == "__main__":
    main()
