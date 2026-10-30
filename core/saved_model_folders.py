"""Dossiers virtuels des modèles enregistrés, propres à chaque fichier .db."""
import sqlite3


def _tables(con):
    con.execute('CREATE TABLE IF NOT EXISTS saved_model_folders (collection_id INTEGER NOT NULL, kind TEXT NOT NULL, path TEXT NOT NULL, PRIMARY KEY(collection_id,kind,path))')
    con.execute('CREATE TABLE IF NOT EXISTS saved_model_locations (collection_id INTEGER NOT NULL, kind TEXT NOT NULL, name TEXT NOT NULL, folder TEXT NOT NULL DEFAULT "", PRIMARY KEY(collection_id,kind,name))')


def _scope(collection_id, kind):
    if kind not in {'etat', 'requete', 'tableau'}:
        raise ValueError('Type de modèle inconnu')
    return int(collection_id), kind


def normalize(path):
    parts = [part.strip() for part in str(path or '').replace('\\', '/').split('/')]
    if any(part in {'.', '..'} for part in parts):
        raise ValueError('Nom de dossier invalide.')
    return '/'.join(part for part in parts if part)


def folders(db, collection_id, kind):
    with sqlite3.connect(db) as con:
        _tables(con)
        return [row[0] for row in con.execute('SELECT path FROM saved_model_folders WHERE collection_id=? AND kind=? ORDER BY path COLLATE NOCASE', _scope(collection_id,kind))]


def folder_for(db, collection_id, kind, name):
    with sqlite3.connect(db) as con:
        _tables(con)
        row = con.execute('SELECT folder FROM saved_model_locations WHERE collection_id=? AND kind=? AND name=?', (*_scope(collection_id,kind), name)).fetchone()
        return row[0] if row else ''


def create_folder(db, collection_id, kind, path):
    path = normalize(path)
    if not path: return
    with sqlite3.connect(db) as con:
        _tables(con)
        bits = path.split('/')
        for index in range(1, len(bits)+1):
            con.execute('INSERT OR IGNORE INTO saved_model_folders VALUES (?,?,?)', (*_scope(collection_id,kind), '/'.join(bits[:index])))


def assign(db, collection_id, kind, name, folder):
    folder = normalize(folder)
    if folder: create_folder(db,collection_id,kind,folder)
    with sqlite3.connect(db) as con:
        _tables(con)
        con.execute('INSERT INTO saved_model_locations VALUES (?,?,?,?) ON CONFLICT(collection_id,kind,name) DO UPDATE SET folder=excluded.folder', (*_scope(collection_id,kind),name,folder))


def rename_item(db, collection_id, kind, old, new):
    folder=folder_for(db,collection_id,kind,old)
    with sqlite3.connect(db) as con:
        _tables(con)
        con.execute('DELETE FROM saved_model_locations WHERE collection_id=? AND kind=? AND name=?', (*_scope(collection_id,kind),old))
    assign(db,collection_id,kind,new,folder)


def delete_item(db, collection_id, kind, name):
    with sqlite3.connect(db) as con:
        _tables(con)
        con.execute('DELETE FROM saved_model_locations WHERE collection_id=? AND kind=? AND name=?', (*_scope(collection_id,kind),name))


def rename_folder(db, collection_id, kind, old, new):
    old, new = normalize(old), normalize(new)
    if not old or not new or new == old or new.startswith(old+'/'):
        raise ValueError('Choisissez un autre emplacement pour ce dossier.')
    with sqlite3.connect(db) as con:
        _tables(con)
        scope=_scope(collection_id,kind)
        existing={row[0] for row in con.execute('SELECT path FROM saved_model_folders WHERE collection_id=? AND kind=?',scope)}
        affected={p for p in existing if p == old or p.startswith(old+'/')}
        if old not in affected: raise ValueError('Dossier introuvable.')
        moved={p: new+p[len(old):] for p in affected}
        if any(dest in existing-affected for dest in moved.values()): raise ValueError('Ce dossier existe déjà.')
        for p in affected: con.execute('DELETE FROM saved_model_folders WHERE collection_id=? AND kind=? AND path=?',(*scope,p))
        for dest in moved.values():
            bits=dest.split('/')
            for i in range(1,len(bits)+1):
                con.execute('INSERT OR IGNORE INTO saved_model_folders VALUES (?,?,?)',(*scope,'/'.join(bits[:i])))
        rows=list(con.execute('SELECT name,folder FROM saved_model_locations WHERE collection_id=? AND kind=?',scope))
        for name,folder in rows:
            if folder == old or folder.startswith(old+'/'):
                con.execute('UPDATE saved_model_locations SET folder=? WHERE collection_id=? AND kind=? AND name=?',(new+folder[len(old):],*scope,name))


def remove_folder(db, collection_id, kind, path):
    path=normalize(path)
    with sqlite3.connect(db) as con:
        _tables(con)
        scope=_scope(collection_id,kind)
        if con.execute('SELECT 1 FROM saved_model_locations WHERE collection_id=? AND kind=? AND (folder=? OR folder LIKE ?)',(*scope,path,path+'/%')).fetchone():
            raise ValueError('Déplacez d’abord les modèles contenus dans ce dossier.')
        con.execute('DELETE FROM saved_model_folders WHERE collection_id=? AND kind=? AND (path=? OR path LIKE ?)',(*scope,path,path+'/%'))
