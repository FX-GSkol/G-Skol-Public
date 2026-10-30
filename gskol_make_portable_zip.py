from __future__ import annotations
import sys
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


def long_path(path: Path) -> Path:
    absolute = str(path.resolve())
    if sys.platform != "win32" or absolute.startswith("\\\\?\\"):
        return Path(absolute)
    if absolute.startswith("\\\\"):
        return Path("\\\\?\\UNC\\" + absolute[2:])
    return Path("\\\\?\\" + absolute)


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: gskol_make_portable_zip.py DOSSIER_SOURCE FICHIER_ZIP")
        return 2
    source = long_path(Path(sys.argv[1]))
    target = long_path(Path(sys.argv[2]))
    if not source.is_dir():
        print(f"Dossier source introuvable : {source}")
        return 3
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        target.unlink()
    with ZipFile(target, "w", ZIP_DEFLATED, allowZip64=True) as archive:
        for path in source.rglob("*"):
            if path.is_file():
                archive.write(path, path.relative_to(source))
    print(f"ZIP cree : {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
