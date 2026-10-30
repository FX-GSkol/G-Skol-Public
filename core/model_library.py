#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bibliothèques locales de modèles MM3.

Chaque famille possède sa bibliothèque. Les sous-dossiers restent entièrement
au choix de l'utilisateur. Les fichiers sont JSON afin de rester inspectables
et échangeables entre installations MM3.
"""
from __future__ import annotations

import json
from pathlib import Path

LIBRARY_FOLDERS = {
    "fiche": "Modèles de Fiches",
    "tableau": "Modèles de Tableaux",
    "requete": "Modèles de Requêtes",
    "etat": "Modèles d'États",
}


def workspace_root_from_database(database_path) -> Path:
    # La bibliothèque appartient à l'installation, même si une collection
    # ouverte avec « Parcourir » réside sur un disque externe.
    from core.paths import WORKSPACE
    return WORKSPACE


def install_example_models(workspace_root) -> int:
    """Ajoute les exemples fournis sans remplacer les modèles personnels."""
    import shutil
    import sys
    # Les constructions portable/installateur copient deja la bibliotheque dans
    # Workspace. Parcourir _internal au demarrage peut echouer sous Windows
    # lorsque le chemin d'extraction depasse la limite des chemins classiques.
    if getattr(sys, "frozen", False):
        return 0
    source = Path(__file__).resolve().parents[1] / "ModelesBibliotheque"
    if not source.is_dir():
        return 0
    destination = Path(workspace_root) / "Bibliothèques"
    count = 0
    # Ne jamais propager les dossiers aux noms corrompus presents dans certaines anciennes distributions.
    # Seule la bibliotheque officielle canonique est installee au demarrage.
    canonical = source / "Modèles de Fiches" / "Découvrir G-Skol"
    if not canonical.is_dir():
        return 0
    for model in sorted(canonical.glob("*.colmod")):
        target = destination / "Modèles de Fiches" / "Découvrir G-Skol" / model.name
        if target.exists():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(model, target)
        count += 1
    return count


def _fold_library_name(value: str) -> str:
    """Normalise un nom de dossier pour reconnaître les éléments natifs G-Skol."""
    import unicodedata
    text = unicodedata.normalize("NFKD", str(value or ""))
    return "".join(ch for ch in text if not unicodedata.combining(ch)).casefold()


def is_native_library_path(path, root) -> bool:
    """Vrai pour le dossier « Découvrir G-Skol » et tout ce qu'il contient.

    Les modèles livrés par G-Skol sont des patrons protégés. Ils peuvent être
    ouverts/appliqués, mais jamais renommés, déplacés, supprimés ou écrasés.
    Toute conservation d'une variante passe par « Enregistrer sous… ».
    """
    try:
        rel = Path(path).resolve().relative_to(Path(root).resolve())
    except (OSError, ValueError):
        return False
    if not rel.parts:
        return False
    first = _fold_library_name(rel.parts[0])
    return ("g-skol" in first or "col-div" in first) and ("decouvrir" in first or "discover" in first)



def native_library_display_name(path, root, language: str = "fr") -> str:
    """Nom d’affichage stable du dossier natif, sans renommer le dossier physique historique."""
    if not is_native_library_path(path, root):
        return Path(path).name
    try:
        rel = Path(path).resolve().relative_to(Path(root).resolve())
    except (OSError, ValueError):
        return Path(path).name
    if len(rel.parts) != 1:
        return Path(path).name
    return "Discover G-Skol" if str(language or "fr").lower().startswith("en") else "Découvrir G-Skol"


def library_sort_key(path, root):
    """Le dossier natif G-Skol reste toujours en tête, puis tri alphabétique normal."""
    return (0 if is_native_library_path(path, root) else 1, Path(path).name.casefold())

def library_root(workspace_root, kind: str) -> Path:
    folder = LIBRARY_FOLDERS[kind]
    root = Path(workspace_root) / "Bibliothèques" / folder
    root.mkdir(parents=True, exist_ok=True)
    return root


def write_model(path, *, kind: str, name: str, payload: dict, source_collection: str = "", field_manifest: dict | None = None) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    envelope = {
        "format": "G-Skol modèle",
        "format_version": 1,
        "kind": kind,
        "name": str(name or target.stem),
        "source_collection": str(source_collection or ""),
        "payload": payload,
        "field_manifest": dict(field_manifest or {}),
    }
    target.write_text(json.dumps(envelope, ensure_ascii=False, indent=2), encoding="utf-8")


def read_model(path, *, expected_kind: str | None = None) -> dict:
    """Lit et valide une enveloppe de modèle G-Skol."""
    source = Path(path)
    data = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("format") != "G-Skol modèle":
        raise ValueError("Ce fichier n’est pas un modèle G-Skol valide.")
    kind = str(data.get("kind") or "")
    if expected_kind and kind != expected_kind:
        raise ValueError("Ce modèle appartient à une autre bibliothèque MM3.")
    payload = data.get("payload")
    if not isinstance(payload, dict):
        raise ValueError("Le contenu de ce modèle est incomplet ou invalide.")
    return data


def collect_model_field_keys(kind: str, payload: dict) -> list[str]:
    """Retourne les clés de champs réellement utilisés par un modèle.

    Pour une Fiche, la liste *visible* est l'autorité : un champ seulement
    présent dans la palette de la collection source ne fait pas partie du
    modèle enregistré. Cela évite qu'un modèle Sables transporte les champs
    Minéraux/Cantal simplement parce qu'ils existent encore dans la palette.
    """
    kind = str(kind or "")
    if not isinstance(payload, dict):
        return []

    if kind == "fiche":
        visible = payload.get("visible") or {}
        if isinstance(visible, dict):
            active = [str(k) for k, v in visible.items() if k and bool(v)]
        else:
            active = [str(k) for k in (visible or []) if k]

        # Présentation dans l'ordre réel de tabulation du modèle, ce qui rend
        # la fenêtre Correspondance beaucoup plus lisible pour l'utilisateur.
        tab = payload.get("tab_positions") or {}
        pos = payload.get("positions") or {}
        def order_key(k: str):
            try:
                t = int(tab.get(k))
            except Exception:
                t = 10**9
            try:
                p = int(pos.get(k))
            except Exception:
                p = 10**9
            return (t, p, k.casefold())
        return sorted(dict.fromkeys(active), key=order_key)

    keys: set[str] = set()
    if kind == "requete":
        for c in payload.get("criteria", []) or []:
            if isinstance(c, dict) and c.get("field"):
                keys.add(str(c["field"]))
    elif kind == "tableau":
        keys.update(str(x) for x in payload.get("fields", []) or [] if x)
        widths = payload.get("widths") or {}
        if isinstance(widths, dict): keys.update(str(k) for k in widths if k)
        for c in payload.get("filters", []) or []:
            if isinstance(c, dict) and c.get("field"): keys.add(str(c["field"]))
        sort = payload.get("sort") or {}
        if isinstance(sort, dict) and sort.get("field"): keys.add(str(sort["field"]))
        for c in payload.get("query", []) or []:
            if isinstance(c, dict) and c.get("field"): keys.add(str(c["field"]))
        aligns = payload.get("column_alignments") or {}
        if isinstance(aligns, dict): keys.update(str(k) for k in aligns if k)
    elif kind == "etat":
        # Les États possèdent plusieurs formes (détaillé / résumé) et les
        # versions historiques n'ont pas toutes rangé les champs au même endroit.
        # On collecte donc toutes les références de champs réellement utilisées.
        for name in ("fields", "summary_fields", "detail_groupings"):
            block = payload.get(name, []) or []
            if isinstance(block, (list, tuple)):
                keys.update(str(x) for x in block if x and str(x) != "__acquisition_year__")
        for name in ("group_field", "second_group_field"):
            value = payload.get(name)
            if value and str(value) != "__acquisition_year__":
                keys.add(str(value))
        for name in ("detail_column_alignments", "summary_column_alignments", "summary_treatments"):
            block = payload.get(name) or {}
            if isinstance(block, dict):
                keys.update(str(k) for k in block if k and str(k) not in {"__group__", "__acquisition_year__"})
        atelier = payload.get("atelier_style") or {}
        if isinstance(atelier, dict):
            repeat = atelier.get("repeat_master_field")
            if repeat and str(repeat) != "__acquisition_year__":
                keys.add(str(repeat))
        layout = payload.get("layout") or {}
        if isinstance(layout, dict):
            widths = layout.get("column_widths") or {}
            if isinstance(widths, dict):
                keys.update(str(k) for k in widths if k and str(k) not in {"__group__", "__acquisition_year__"})
            sort_field = layout.get("sort_field")
            if sort_field and str(sort_field) != "__acquisition_year__":
                keys.add(str(sort_field))
    return sorted(keys)


def build_field_manifest(model_manager, collection_id: int, field_keys: list[str]) -> dict:
    """Décrit les champs d'un modèle pour permettre son rappel dans une autre collection."""
    try:
        from core.field_catalog import FIELD_BY_KEY
    except Exception:
        FIELD_BY_KEY = {}
    custom = model_manager.custom_field_map(int(collection_id))
    overrides = {}
    try:
        import sqlite3
        with sqlite3.connect(model_manager.database_path) as con:
            for row in con.execute(
                "SELECT field_key, custom_label FROM collection_model_fields WHERE collection_id=? AND custom_label IS NOT NULL",
                (int(collection_id),),
            ):
                overrides[str(row[0])] = str(row[1] or "")
    except Exception:
        pass
    result = {}
    for key in field_keys:
        key = str(key or "")
        if not key: continue
        if key in custom:
            info = dict(custom[key])
            result[key] = {
                "key": key,
                "label": str(info.get("label") or key),
                "field_type": str(info.get("field_type") or "text"),
                "custom": True,
                "date_format": str(info.get("date_format") or "JJ/MM/AAAA"),
            }
        else:
            spec = FIELD_BY_KEY.get(key)
            result[key] = {
                "key": key,
                "label": str(overrides.get(key) or (getattr(spec, "label", None) if spec else None) or key),
                "field_type": str(getattr(spec, "field_type", "text") if spec else "text"),
                "custom": False,
                "date_format": "JJ/MM/AAAA",
            }
    return result


def remap_model_payload(kind: str, payload: dict, mapping: dict[str, str | None]) -> dict:
    """Applique une correspondance de champs à une copie d'un modèle."""
    from copy import deepcopy
    data = deepcopy(payload)
    def mapped(k):
        if k is None: return None
        k = str(k)
        return mapping.get(k, k)
    def remap_dict_keys(block):
        if not isinstance(block, dict): return block
        out = {}
        for k, v in block.items():
            nk = mapped(k)
            if nk: out[nk] = v
        return out
    kind = str(kind or "")
    if kind == "fiche":
        # 11.7.55 — un modèle de Fiche est un instantané autonome.
        # Les anciennes versions pouvaient conserver, dans visual_positions /
        # visual_sizes / field_styles, des champs MASQUÉS provenant de la
        # collection source. Ils n'apparaissaient pas dans la palette cochée,
        # mais étaient quand même réinjectés au rappel du modèle et pouvaient
        # déplacer/recomposer la fiche suivant la collection destinataire.
        # L'autorité est donc STRICTEMENT la liste visible=True du modèle.
        visible_block = data.get("visible") or {}
        if isinstance(visible_block, dict):
            active_source_keys = {str(k) for k, v in visible_block.items() if k and bool(v)}
        else:
            active_source_keys = {str(k) for k in (visible_block or []) if k}

        def remap_active_dict(block):
            if not isinstance(block, dict):
                return block
            out = {}
            for k, v in block.items():
                sk = str(k)
                if sk not in active_source_keys:
                    continue
                nk = mapped(sk)
                if nk:
                    out[nk] = v
            return out

        for section in (
            "visible", "labels", "blocks", "positions", "tab_positions",
            "visual_positions", "visual_sizes", "field_styles"
        ):
            if section in data:
                data[section] = remap_active_dict(data.get(section))

        data["field_masters"] = [
            mapped(k) for k in data.get("field_masters", []) or []
            if str(k) in active_source_keys and mapped(k)
        ]
        links = data.get("field_links") or {}
        if isinstance(links, dict):
            out = {}
            for k, v in links.items():
                sk, sv = str(k), str(v)
                if sk not in active_source_keys or sv not in active_source_keys:
                    continue
                nk, nv = mapped(sk), mapped(sv)
                if nk and nv:
                    out[nk] = nv
            data["field_links"] = out
    elif kind == "requete":
        kept=[]
        for c in data.get("criteria", []) or []:
            if not isinstance(c, dict): continue
            nc=deepcopy(c); nf=mapped(nc.get("field"))
            if nf: nc["field"]=nf; kept.append(nc)
        data["criteria"]=kept
    elif kind == "tableau":
        data["fields"]=[mapped(k) for k in data.get("fields", []) or [] if mapped(k)]
        data["widths"]=remap_dict_keys(data.get("widths") or {})
        for name in ("filters", "query"):
            kept=[]
            for c in data.get(name, []) or []:
                if not isinstance(c, dict): continue
                nc=deepcopy(c); nf=mapped(nc.get("field"))
                if nf: nc["field"]=nf; kept.append(nc)
            data[name]=kept
        sort=data.get("sort") or {}
        if isinstance(sort, dict) and sort.get("field"):
            nf=mapped(sort.get("field")); sort=dict(sort); sort["field"]=nf
            if not nf: sort={"field":None,"order":str(sort.get("order") or "asc")}
            data["sort"]=sort
        data["column_alignments"]=remap_dict_keys(data.get("column_alignments") or {})
    elif kind == "etat":
        for name in ("fields", "summary_fields", "detail_groupings"):
            data[name]=[mapped(k) for k in data.get(name, []) or [] if mapped(k)]
        for name in ("group_field", "second_group_field"):
            if name in data: data[name]=mapped(data.get(name))
        for name in ("detail_column_alignments", "summary_column_alignments", "summary_treatments"):
            data[name]=remap_dict_keys(data.get(name) or {})
    return data
