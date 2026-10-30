"""Sauvegardes volontaires vérifiées du Workspace MM3."""
from __future__ import annotations

import hashlib
from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
import tempfile
from datetime import datetime
from zipfile import ZipFile, ZIP_DEFLATED


_SQLITE_EXTENSIONS = {'.coldb', '.db', '.sqlite', '.sqlite3'}


def _digest(stream):
    h = hashlib.sha256()
    for chunk in iter(lambda: stream.read(1024 * 1024), b''):
        h.update(chunk)
    return h.hexdigest()


def _source_files(workspace):
    for path in sorted(workspace.rglob('*')):
        if not path.is_file() or path.is_symlink():
            continue
        relative = path.relative_to(workspace)
        if relative.parts[0].casefold() == 'sauvegardes':
            continue
        if path.suffix.casefold() in {'.sqlite-wal', '.sqlite-shm', '.db-wal', '.db-shm'}:
            continue
        if path.name.endswith(('-wal', '-shm', '-journal')) and path.with_name(path.name.rsplit('-', 1)[0]).suffix.casefold() in _SQLITE_EXTENSIONS:
            continue
        yield path, relative.as_posix()


def create_workspace_backup(workspace: Path, destination: Path) -> dict:
    """Copie toutes les données hors Sauvegardes, y compris les bases SQLite actives."""
    workspace, destination = Path(workspace).resolve(), Path(destination).resolve()
    if not workspace.is_dir():
        raise ValueError('Le dossier Workspace est introuvable.')
    if destination.exists():
        raise FileExistsError('Une sauvegarde portant ce nom existe déjà.')
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    entries = []
    try:
        with tempfile.NamedTemporaryFile(prefix='.mm3-backup-', suffix='.zip', dir=destination.parent, delete=False) as handle:
            temporary = Path(handle.name)
        with ZipFile(temporary, 'w', compression=ZIP_DEFLATED, compresslevel=6, allowZip64=True) as archive:
            for source, name in _source_files(workspace):
                if source.suffix.casefold() in _SQLITE_EXTENSIONS:
                    with tempfile.NamedTemporaryFile(prefix='mm3-snapshot-', suffix='.db', delete=False) as snapshot:
                        snapshot_path = Path(snapshot.name)
                    try:
                        # sqlite3.Connection.__exit__ valide la transaction mais ne ferme
                        # pas la connexion. Windows interdit alors de supprimer ce fichier.
                        with closing(sqlite3.connect(f'file:{source.as_posix()}?mode=ro', uri=True)) as original:
                            with closing(sqlite3.connect(snapshot_path)) as consistent:
                                original.backup(consistent)
                                integrity = consistent.execute('PRAGMA quick_check').fetchone()
                                if not integrity or integrity[0] != 'ok':
                                    raise ValueError(f'Base illisible : {name}')
                        with snapshot_path.open('rb') as stream:
                            fingerprint = _digest(stream)
                        archive.write(snapshot_path, 'Workspace/' + name)
                    finally:
                        snapshot_path.unlink(missing_ok=True)
                else:
                    with source.open('rb') as stream:
                        fingerprint = _digest(stream)
                    archive.write(source, 'Workspace/' + name)
                # Ne jamais relire le ZIP avant sa fermeture : sous Windows,
                # cela déplace son pointeur d'écriture et corrompt ses en-têtes.
                entries.append({'path': name, 'sha256': fingerprint})
            manifest = {'format': 'MM3 Workspace backup', 'version': 1,
                        'created_at': datetime.now().isoformat(timespec='seconds'), 'files': entries}
            archive.writestr('manifest.json', json.dumps(manifest, ensure_ascii=False, indent=2))
        with ZipFile(temporary) as archive:
            if archive.testzip() is not None:
                raise ValueError('La sauvegarde contient une entrée endommagée.')
            for entry in entries:
                with archive.open('Workspace/' + entry['path']) as stream:
                    if _digest(stream) != entry['sha256']:
                        raise ValueError(f"Échec de vérification : {entry['path']}")
        os.replace(temporary, destination)
        return manifest
    except Exception:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        raise


def workspace_backup_inventory(workspace: Path) -> dict:
    """Inventaire stable de la portée d'une sauvegarde complète du Workspace."""
    workspace = Path(workspace).resolve()
    if not workspace.is_dir():
        raise ValueError('Le dossier Workspace est introuvable.')
    collection_dir = workspace / 'Collections'
    collections = sorted((p for p in collection_dir.rglob('*') if p.is_file() and not p.is_symlink()
                          and p.suffix.casefold() == '.coldb'
                          and p.name.casefold() not in {'micromin3.db', '.mm3-system.db'}),
                         key=lambda p: str(p).casefold()) if collection_dir.is_dir() else []
    return {'collections': collections, 'files': list(_source_files(workspace))}


def create_native_workspace_backup(workspace: Path, destination: Path, inventory: dict | None = None) -> dict:
    """Crée un dossier autonome avec les .db natifs et les autres fichiers du Workspace."""
    workspace, destination = Path(workspace).resolve(), Path(destination).resolve()
    if destination.exists():
        raise FileExistsError('Une sauvegarde portant ce nom existe déjà.')
    if destination == workspace or (workspace in destination.parents and not destination.is_relative_to(workspace / 'Sauvegardes')):
        raise ValueError('Dans le Workspace, choisissez uniquement le dossier Sauvegardes comme destination.')
    # L'inventaire affiché dans la boîte de dialogue peut devenir périmé pendant
    # que l'utilisateur choisit la destination (journaux, fichiers temporaires, etc.).
    # On le reconstruit juste avant la copie afin de ne jamais tenter de sauvegarder
    # un fichier qui a déjà disparu.
    inventory = workspace_backup_inventory(workspace)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix='.mm3-backup-', dir=destination.parent))
    entries = []
    try:
        for source, name in inventory['files']:
            source = Path(source)
            # Certains fichiers techniques (journaux/temporaire) peuvent être supprimés
            # par MM3 entre l'inventaire et leur copie. Ils ne doivent pas faire échouer
            # toute une sauvegarde : s'ils n'existent plus, ils n'appartiennent plus à
            # l'état du Workspace que l'on sauvegarde.
            if not source.is_file():
                continue
            target = temporary / name
            target.parent.mkdir(parents=True, exist_ok=True)
            try:
                if source.suffix.casefold() in _SQLITE_EXTENSIONS:
                    with closing(sqlite3.connect(f'file:{source.resolve().as_posix()}?mode=ro', uri=True)) as original:
                        with closing(sqlite3.connect(target)) as copy:
                            original.backup(copy)
                            check = copy.execute('PRAGMA quick_check').fetchone()
                            if not check or check[0] != 'ok':
                                raise ValueError(f'Base illisible : {name}')
                else:
                    import shutil
                    shutil.copy2(source, target)
            except FileNotFoundError:
                # Course bénigne avec un fichier volatile supprimé pendant copy2.
                # Une base/collection disparue est en revanche une anomalie réelle.
                if source.suffix.casefold() in _SQLITE_EXTENSIONS:
                    raise
                target.unlink(missing_ok=True)
                continue
            with target.open('rb') as stream:
                digest = _digest(stream)
            entries.append({'path': name, 'sha256': digest})
        manifest = {'format': 'MM3 native Workspace backup', 'version': 2,
                    'created_at': datetime.now().isoformat(timespec='seconds'),
                    'collections': [str(p.relative_to(workspace)) for p in inventory['collections']],
                    'files': entries}
        (temporary / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
        for entry in entries:
            with (temporary / entry['path']).open('rb') as stream:
                if _digest(stream) != entry['sha256']:
                    raise ValueError(f"Échec de vérification : {entry['path']}")
        temporary.rename(destination)
        return manifest
    except Exception:
        import shutil
        shutil.rmtree(temporary, ignore_errors=True)
        raise

def create_selected_database_backup(sources, destination):
    """Copies atomiques de bases MM3 complètes, lisibles individuellement."""
    import shutil
    sources = [Path(p).resolve() for p in sources]
    if not sources or len(sources) != len(set(sources)):
        raise ValueError("Sélectionnez au moins une base distincte.")
    destination = Path(destination).expanduser().resolve()
    if destination.exists():
        raise FileExistsError("Ce dossier de sauvegarde existe déjà.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".mm3-collections-", dir=destination.parent))
    entries, used = [], set()
    try:
        for source in sources:
            if not source.is_file():
                raise FileNotFoundError(f"Base introuvable : {source}")
            # Une sélection correspond à un fichier .coldb entier, même s'il contient plusieurs collections.
            base = source.stem
            name = source.name
            number = 2
            while name.casefold() in used:
                name = f"{base} - {number}{source.suffix}"
                number += 1
            used.add(name.casefold())
            target = temporary / name
            with closing(sqlite3.connect(f"file:{source.as_posix()}?mode=ro", uri=True)) as original:
                with closing(sqlite3.connect(target)) as copy:
                    original.backup(copy)
                    check = copy.execute("PRAGMA quick_check").fetchone()
                    if not check or check[0] != "ok":
                        raise ValueError(f"Base illisible : {source.name}")
            with target.open("rb") as stream:
                digest = _digest(stream)
            entries.append({"source": str(source), "file": name, "sha256": digest})
        for entry in entries:
            with (temporary / entry["file"]).open("rb") as stream:
                if _digest(stream) != entry["sha256"]:
                    raise ValueError(f"Échec de vérification : {entry['file']}")
        (temporary / "LISEZ-MOI.txt").write_text(
            "Chaque fichier .coldb est une collection G-Skol autonome. Ouvrez-le dans G-Skol.\n"
            "Le dossier ne contient que les bases sélectionnées et cette notice.\n",
            encoding="utf-8")
        temporary.rename(destination)
        return [destination / entry["file"] for entry in entries]
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
