"""Copy an explicitly curated public model library; never read the private Workspace."""
from __future__ import annotations
import shutil
import sys
from pathlib import Path

def main() -> int:
    if len(sys.argv) != 4 or sys.argv[1] != "--public":
        print("Usage: gskol_copy_library.py --public PUBLIC_MODELS_DIR DEST_WORKSPACE")
        return 2
    source = Path(sys.argv[2]).resolve()
    destination = Path(sys.argv[3]).resolve() / "Bibliothèques" / "Modèles de Fiches"
    if not source.is_dir() or source.is_symlink():
        print(f"Dossier public absent ou non valide : {source}")
        return 3
    if destination.exists():
        print(f"Destination déjà présente : {destination}")
        return 4
    if any(p.is_symlink() for p in source.rglob("*")):
        print("Liens symboliques interdits dans la bibliothèque publique")
        return 5
    shutil.copytree(source, destination)
    print(f"Bibliothèque publique copiée : {destination}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
