from pathlib import Path
def ensure_ini(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text("[MM3]\nlanguage=fr\n",encoding="utf-8")
        return True
    return False
