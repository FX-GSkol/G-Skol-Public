#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sélecteur MM3 pour l'enregistrement et la gestion d'une bibliothèque de modèles."""
from __future__ import annotations

import shutil
import unicodedata
from pathlib import Path

from PySide6.QtCore import Qt
from core.i18n import tr
from core.model_library import is_native_library_path, native_library_display_name, library_sort_key

from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QComboBox, QDialog, QHBoxLayout, QHeaderView, QInputDialog, QLabel, QLineEdit, QMessageBox,
    QPushButton, QTableWidget, QTableWidgetItem, QTreeWidget, QTreeWidgetItem, QVBoxLayout,
)


def _ui_language(parent):
    widget = parent
    while widget is not None:
        value = getattr(widget, "language", None)
        if value:
            return str(value)
        try:
            widget = widget.parentWidget()
        except Exception:
            break
    return "fr"

def _t(parent, text):
    return tr(text, _ui_language(parent))


_NATIVE_FOLDER_EN = {
    "Cartes postales": "Postcards",
    "Étiquettes- Documents graphiques": "Labels - Graphic documents",
    "Étiquettes - Documents graphiques": "Labels - Graphic documents",
    "Fossiles": "Fossils",
    "Livres-Documents": "Books - Documents",
    "Minéraux": "Minerals",
    "Monnaie-Médailles-Jetons": "Coins - Medals - Tokens",
    "Objets de collection": "Collectibles",
    "Sables": "Sands",
    "Timbres": "Stamps",
}
_NATIVE_MODEL_EN = {
    "Micro Minéraux": "Microminerals",
    "Micro minéraux": "Microminerals",
}

def _native_display_name(parent, path, root):
    name = Path(path).stem if Path(path).is_file() else Path(path).name
    if not str(_ui_language(parent)).lower().startswith("en"):
        return name
    if not is_native_library_path(path, root):
        return name
    return _NATIVE_MODEL_EN.get(name, _NATIVE_FOLDER_EN.get(name, name))

def _get_text_fr(parent, title, label, text=""):
    dialog = QInputDialog(parent)
    dialog.setWindowTitle(_t(parent, title))
    dialog.setLabelText(_t(parent, label))
    dialog.setTextValue(text)
    dialog.setOkButtonText("OK")
    dialog.setCancelButtonText(_t(parent, "Annuler"))
    if dialog.exec() == QDialog.DialogCode.Accepted:
        return dialog.textValue(), True
    return dialog.textValue(), False


class WheelOnlyWhenOpenComboBox(QComboBox):
    """La roulette ne change la valeur que lorsque la liste est réellement ouverte."""
    def wheelEvent(self, event) -> None:  # noqa: N802
        try:
            opened = self.view().isVisible()
        except Exception:
            opened = False
        if opened:
            super().wheelEvent(event)
        else:
            event.ignore()


def choose_model_save_path(parent, root, default_name: str, library_title: str):
    """Choisit un dossier de bibliothèque et permet d'y gérer dossiers et modèles."""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)

    dialog = QDialog(parent)
    dialog.setWindowTitle(f"Enregistrer sous — {library_title}")
    dialog.setModal(True)
    dialog.resize(760, 540)

    layout = QVBoxLayout(dialog)
    layout.setContentsMargins(14, 12, 14, 12)
    layout.setSpacing(8)

    intro = QLabel(
        "Choisissez le dossier de classement. Les dossiers et les modèles déjà enregistrés "
        "sont visibles ci-dessous. Vous pouvez créer, renommer ou supprimer vos classements."
    )
    intro.setWordWrap(True)
    layout.addWidget(intro)

    tree = QTreeWidget()
    tree.setHeaderLabel(library_title)
    tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    layout.addWidget(tree, 1)

    folder_row = QHBoxLayout()
    folder_row.addWidget(QLabel("Dossier sélectionné :"))
    current_folder = QLabel(str(root))
    current_folder.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    folder_row.addWidget(current_folder, 1)
    layout.addLayout(folder_row)

    manage_row = QHBoxLayout()
    new_folder_btn = QPushButton("Nouveau dossier…")
    rename_btn = QPushButton("Renommer…")
    delete_btn = QPushButton("Supprimer…")
    manage_row.addWidget(new_folder_btn)
    manage_row.addWidget(rename_btn)
    manage_row.addWidget(delete_btn)
    manage_row.addStretch(1)
    layout.addLayout(manage_row)

    name_row = QHBoxLayout()
    name_row.addWidget(QLabel("Nom du modèle :"))
    name_edit = QLineEdit(str(default_name or "Modèle"))
    name_edit.selectAll()
    name_row.addWidget(name_edit, 1)
    layout.addLayout(name_row)

    buttons = QHBoxLayout()
    buttons.addStretch(1)
    save_btn = QPushButton("Enregistrer")
    cancel_btn = QPushButton("Annuler")
    buttons.addWidget(save_btn)
    buttons.addWidget(cancel_btn)
    layout.addLayout(buttons)

    def item_path(item: QTreeWidgetItem | None) -> Path:
        if item is None:
            return root
        value = item.data(0, Qt.ItemDataRole.UserRole)
        return Path(str(value or root))

    def item_kind(item: QTreeWidgetItem | None) -> str:
        if item is None:
            return "folder"
        return str(item.data(0, Qt.ItemDataRole.UserRole + 1) or "folder")

    def selected_folder() -> Path:
        item = tree.currentItem()
        path = item_path(item)
        return path if item_kind(item) == "folder" else path.parent

    def add_children(parent_item: QTreeWidgetItem, folder: Path) -> None:
        try:
            entries = list(folder.iterdir())
        except OSError:
            entries = []
        dirs = sorted((p for p in entries if p.is_dir()), key=lambda p: library_sort_key(p, root))
        models = sorted((p for p in entries if p.is_file() and p.suffix.casefold() == ".colmod"), key=lambda p: p.name.casefold())
        for child in dirs:
            item = QTreeWidgetItem([f"{'🔒 ' if is_native_library_path(child, root) else '📁 '}{native_library_display_name(child, root, _ui_language(dialog))}"])
            item.setData(0, Qt.ItemDataRole.UserRole, str(child))
            item.setData(0, Qt.ItemDataRole.UserRole + 1, "folder")
            parent_item.addChild(item)
            add_children(item, child)
        for model in models:
            item = QTreeWidgetItem([f"{'🔒 ' if is_native_library_path(model, root) else '📄 '}{_native_display_name(dialog, model, root)}"])
            item.setData(0, Qt.ItemDataRole.UserRole, str(model))
            item.setData(0, Qt.ItemDataRole.UserRole + 1, "model")
            parent_item.addChild(item)

    def populate(select_path: Path | None = None) -> None:
        tree.clear()
        root_item = QTreeWidgetItem([f"📁 {library_title} (racine)"])
        root_item.setData(0, Qt.ItemDataRole.UserRole, str(root))
        root_item.setData(0, Qt.ItemDataRole.UserRole + 1, "folder")
        tree.addTopLevelItem(root_item)
        add_children(root_item, root)
        root_item.setExpanded(True)

        wanted = str((select_path or root).resolve())
        found = None
        stack = [root_item]
        while stack:
            it = stack.pop()
            try:
                current = str(item_path(it).resolve())
            except OSError:
                current = str(item_path(it))
            if current == wanted:
                found = it
                break
            for i in range(it.childCount()):
                stack.append(it.child(i))
        tree.setCurrentItem(found or root_item)
        if found:
            p = found.parent()
            while p is not None:
                p.setExpanded(True)
                p = p.parent()

    def update_selection() -> None:
        item = tree.currentItem()
        current_folder.setText(str(selected_folder()))
        is_root = item is not None and item.parent() is None
        rename_btn.setEnabled(item is not None and not is_root)
        delete_btn.setEnabled(item is not None and not is_root)
        if item is not None and item_kind(item) == "model":
            name_edit.setText(item_path(item).stem)
            name_edit.selectAll()

    tree.currentItemChanged.connect(lambda *_: update_selection())

    def create_folder() -> None:
        base = selected_folder()
        name, ok = _get_text_fr(dialog, "Nouveau dossier", "Nom du nouveau dossier :")
        name = str(name or "").strip()
        if not ok or not name:
            return
        if any(ch in name for ch in '<>:"/\\|?*'):
            QMessageBox.information(dialog, "Nom incorrect", "Le nom contient un caractère interdit par Windows.")
            return
        target = base / name
        try:
            target.mkdir(parents=False, exist_ok=False)
        except FileExistsError:
            QMessageBox.information(dialog, "Dossier existant", "Un dossier de ce nom existe déjà ici.")
            return
        except OSError as exc:
            QMessageBox.critical(dialog, "Création impossible", str(exc))
            return
        populate(target)

    def rename_selected() -> None:
        item = tree.currentItem()
        if item is None or item.parent() is None:
            return
        path = item_path(item)
        kind = item_kind(item)
        old_name = path.stem if kind == "model" else path.name
        label = "Nouveau nom du modèle :" if kind == "model" else "Nouveau nom du dossier :"
        name, ok = _get_text_fr(dialog, "Renommer", label, text=old_name)
        name = str(name or "").strip()
        if not ok or not name or name == old_name:
            return
        if any(ch in name for ch in '<>:"/\\|?*'):
            QMessageBox.information(dialog, "Nom incorrect", "Le nom contient un caractère interdit par Windows.")
            return
        target = path.with_name(f"{name}.colmod" if kind == "model" else name)
        if target.exists():
            QMessageBox.information(dialog, "Nom déjà utilisé", "Un élément de ce nom existe déjà dans ce dossier.")
            return
        try:
            path.rename(target)
        except OSError as exc:
            QMessageBox.critical(dialog, "Renommage impossible", str(exc))
            return
        populate(target)

    def delete_selected() -> None:
        item = tree.currentItem()
        if item is None or item.parent() is None:
            return
        path = item_path(item)
        kind = item_kind(item)
        if kind == "folder":
            text = f"Supprimer le dossier « {path.name} » ?"
            try:
                non_empty = any(path.iterdir())
            except OSError:
                non_empty = False
            if non_empty:
                text += "\n\nATTENTION : tous les sous-dossiers et modèles qu'il contient seront également supprimés."
        else:
            text = f"Supprimer définitivement le modèle « {path.stem} » ?"
        box = QMessageBox(dialog)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("Confirmer la suppression")
        box.setText(text)
        delete_action = box.addButton("Supprimer", QMessageBox.ButtonRole.DestructiveRole)
        cancel_action = box.addButton("Annuler", QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(cancel_action)
        box.exec()
        if box.clickedButton() is not delete_action:
            return
        parent_path = path.parent
        try:
            if kind == "folder":
                shutil.rmtree(path)
            else:
                path.unlink()
        except OSError as exc:
            QMessageBox.critical(dialog, "Suppression impossible", str(exc))
            return
        populate(parent_path if parent_path.exists() else root)

    new_folder_btn.clicked.connect(create_folder)
    rename_btn.clicked.connect(rename_selected)
    delete_btn.clicked.connect(delete_selected)

    result = {"path": None}

    def accept_save() -> None:
        name = name_edit.text().strip()
        if not name:
            QMessageBox.information(dialog, "Nom obligatoire", "Indiquez un nom pour le modèle.")
            return
        if name.lower().endswith(".colmod"):
            name = name[:-9]
        if any(ch in name for ch in '<>:"/\\|?*'):
            QMessageBox.information(dialog, "Nom incorrect", "Le nom contient un caractère interdit par Windows.")
            return
        target = selected_folder() / f"{name}.colmod"
        if is_native_library_path(target, root):
            QMessageBox.information(dialog, _t(dialog, "Modèle natif G-Skol"), _t(dialog, "Les modèles natifs G-Skol sont protégés. Choisissez un autre dossier pour enregistrer votre modèle personnel."))
            return
        if target.exists():
            box = QMessageBox(dialog)
            box.setIcon(QMessageBox.Icon.Question)
            box.setWindowTitle("Modèle existant")
            box.setText(f"« {target.name} » existe déjà.")
            box.setInformativeText("Voulez-vous remplacer ce modèle ?")
            replace_btn = box.addButton("Remplacer", QMessageBox.ButtonRole.AcceptRole)
            cancel_replace_btn = box.addButton("Annuler", QMessageBox.ButtonRole.RejectRole)
            box.setDefaultButton(cancel_replace_btn)
            box.exec()
            if box.clickedButton() is not replace_btn:
                return
        result["path"] = target
        dialog.accept()

    save_btn.clicked.connect(accept_save)
    cancel_btn.clicked.connect(dialog.reject)
    name_edit.returnPressed.connect(accept_save)
    tree.itemDoubleClicked.connect(lambda item, _col: item.setExpanded(not item.isExpanded()) if item_kind(item) == "folder" else None)

    populate(root)
    update_selection()
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return None
    return result["path"]


def choose_model_open_path(parent, root, library_title: str):
    """Choisit et gère un modèle existant dans une bibliothèque MM3.

    11.7.62 — la fenêtre d'ouverture devient aussi un vrai gestionnaire de
    bibliothèque : création de dossier, renommage, déplacement et suppression
    des modèles ET des dossiers, sans passer par « Enregistrer sous ».
    """
    t = lambda text: _t(parent, text)
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    dialog = QDialog(parent)
    dialog.setWindowTitle(f"{t('Ouvrir un modèle')} — {t(library_title)}")
    dialog.setModal(True)
    dialog.resize(820, 580)
    layout = QVBoxLayout(dialog)
    layout.setContentsMargins(14, 12, 14, 12)
    layout.setSpacing(8)

    intro = QLabel(t("Choisissez un modèle. Double-cliquez sur un modèle pour l’ouvrir directement. Vous pouvez aussi créer, renommer, déplacer ou supprimer vos dossiers et modèles."))
    intro.setWordWrap(True)
    layout.addWidget(intro)

    tree = QTreeWidget()
    tree.setHeaderLabel(t(library_title))
    tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    layout.addWidget(tree, 1)

    manage = QHBoxLayout()
    new_folder_btn = QPushButton(t("Nouveau dossier…"))
    rename_btn = QPushButton(t("Renommer…"))
    move_btn = QPushButton(t("Déplacer vers…"))
    delete_btn = QPushButton(t("Supprimer…"))
    manage.addWidget(new_folder_btn)
    manage.addWidget(rename_btn)
    manage.addWidget(move_btn)
    manage.addWidget(delete_btn)
    manage.addStretch(1)
    layout.addLayout(manage)

    buttons = QHBoxLayout()
    buttons.addStretch(1)
    open_btn = QPushButton(t("Ouvrir"))
    cancel_btn = QPushButton(t("Annuler"))
    open_btn.setEnabled(False)
    buttons.addWidget(open_btn)
    buttons.addWidget(cancel_btn)
    layout.addLayout(buttons)

    def item_path(item):
        return Path(str(item.data(0, Qt.ItemDataRole.UserRole) or root)) if item else root

    def item_kind(item):
        return str(item.data(0, Qt.ItemDataRole.UserRole + 1) or "folder") if item else "folder"

    def selected_folder():
        item = tree.currentItem()
        p = item_path(item)
        return p if item_kind(item) == "folder" else p.parent

    def add_children(parent_item, folder):
        try:
            entries = list(folder.iterdir())
        except OSError:
            entries = []
        for child in sorted((x for x in entries if x.is_dir()), key=lambda x: library_sort_key(x, root)):
            it = QTreeWidgetItem([f"{'🔒 ' if is_native_library_path(child, root) else '📁 '}{native_library_display_name(child, root, _ui_language(dialog))}"])
            it.setData(0, Qt.ItemDataRole.UserRole, str(child))
            it.setData(0, Qt.ItemDataRole.UserRole + 1, "folder")
            parent_item.addChild(it)
            add_children(it, child)
        for model in sorted((x for x in entries if x.is_file() and x.suffix.casefold() == ".colmod"), key=lambda x: x.name.casefold()):
            it = QTreeWidgetItem([f"{'🔒 ' if is_native_library_path(model, root) else '📄 '}{_native_display_name(dialog, model, root)}"])
            it.setData(0, Qt.ItemDataRole.UserRole, str(model))
            it.setData(0, Qt.ItemDataRole.UserRole + 1, "model")
            parent_item.addChild(it)

    def populate(select_path=None):
        tree.clear()
        root_item = QTreeWidgetItem(["📁 " + t(library_title) + " " + t("(racine)")])
        root_item.setData(0, Qt.ItemDataRole.UserRole, str(root))
        root_item.setData(0, Qt.ItemDataRole.UserRole + 1, "folder")
        tree.addTopLevelItem(root_item)
        add_children(root_item, root)
        root_item.setExpanded(True)
        wanted = None
        if select_path is not None:
            try:
                wanted = str(Path(select_path).resolve())
            except OSError:
                wanted = str(Path(select_path))
        found = None
        stack = [root_item]
        while stack:
            it = stack.pop()
            try:
                cur = str(item_path(it).resolve())
            except OSError:
                cur = str(item_path(it))
            if wanted and cur == wanted:
                found = it
                break
            for i in range(it.childCount()):
                stack.append(it.child(i))
        tree.setCurrentItem(found or root_item)
        if found:
            par = found.parent()
            while par is not None:
                par.setExpanded(True)
                par = par.parent()
        update_buttons()

    def update_buttons(*_):
        item = tree.currentItem()
        is_model = item is not None and item_kind(item) == "model"
        is_root = item is not None and item.parent() is None
        open_btn.setEnabled(is_model)
        protected = item is not None and is_native_library_path(item_path(item), root)
        rename_btn.setEnabled(item is not None and not is_root and not protected)
        move_btn.setEnabled(item is not None and not is_root and not protected)
        delete_btn.setEnabled(item is not None and not is_root and not protected)
        try:
            new_folder_btn.setEnabled(not is_native_library_path(selected_folder(), root))
        except Exception:
            new_folder_btn.setEnabled(True)

    def valid_name(name):
        return bool(name) and not any(ch in name for ch in '<>:"/\\|?*')

    def create_folder():
        base = selected_folder()
        name, ok = _get_text_fr(dialog, "Nouveau dossier", "Nom du nouveau dossier :")
        name = str(name or "").strip()
        if not ok or not name:
            return
        if not valid_name(name):
            QMessageBox.information(dialog, "Nom incorrect", "Le nom contient un caractère interdit par Windows.")
            return
        target = base / name
        try:
            target.mkdir(parents=False, exist_ok=False)
        except FileExistsError:
            QMessageBox.information(dialog, "Dossier existant", "Un dossier de ce nom existe déjà ici.")
            return
        except OSError as exc:
            QMessageBox.critical(dialog, "Création impossible", str(exc))
            return
        populate(target)

    def rename_selected():
        item = tree.currentItem()
        if item is None or item.parent() is None:
            return
        path = item_path(item)
        if is_native_library_path(path, root):
            return
        kind = item_kind(item)
        old_name = path.stem if kind == "model" else path.name
        label = "Nouveau nom du modèle :" if kind == "model" else "Nouveau nom du dossier :"
        name, ok = _get_text_fr(dialog, "Renommer", label, text=old_name)
        name = str(name or "").strip()
        if not ok or not name or name == old_name:
            return
        if not valid_name(name):
            QMessageBox.information(dialog, "Nom incorrect", "Le nom contient un caractère interdit par Windows.")
            return
        target = path.with_name(f"{name}.colmod" if kind == "model" else name)
        if target.exists():
            QMessageBox.information(dialog, "Nom déjà utilisé", "Un élément de ce nom existe déjà dans ce dossier.")
            return
        try:
            path.rename(target)
        except OSError as exc:
            QMessageBox.critical(dialog, "Renommage impossible", str(exc))
            return
        populate(target)

    def choose_destination(source):
        d = QDialog(dialog)
        d.setWindowTitle("Déplacer vers…")
        d.setModal(True)
        d.resize(600, 460)
        lay = QVBoxLayout(d)
        msg = QLabel("Choisissez le dossier de destination :")
        lay.addWidget(msg)
        folders = QTreeWidget()
        folders.setHeaderLabel(library_title)
        lay.addWidget(folders, 1)

        def add_folder_children(parent_item, folder):
            try:
                children = sorted((x for x in folder.iterdir() if x.is_dir()), key=lambda x: x.name.casefold())
            except OSError:
                children = []
            for child in children:
                it = QTreeWidgetItem([f"📁 {child.name}"])
                it.setData(0, Qt.ItemDataRole.UserRole, str(child))
                parent_item.addChild(it)
                add_folder_children(it, child)

        ri = QTreeWidgetItem(["📁 " + t(library_title) + " " + t("(racine)")])
        ri.setData(0, Qt.ItemDataRole.UserRole, str(root))
        folders.addTopLevelItem(ri)
        add_folder_children(ri, root)
        ri.setExpanded(True)
        folders.setCurrentItem(ri)
        row = QHBoxLayout(); row.addStretch(1)
        okb = QPushButton("Déplacer ici"); cb = QPushButton(t("Annuler"))
        row.addWidget(okb); row.addWidget(cb); lay.addLayout(row)
        result = {"folder": None}

        def accept_dest():
            it = folders.currentItem()
            if it is None:
                return
            dest = Path(str(it.data(0, Qt.ItemDataRole.UserRole) or root))
            # Un dossier ne peut pas être déplacé dans lui-même ni dans un de ses descendants.
            if source.is_dir():
                try:
                    dest.resolve().relative_to(source.resolve())
                    QMessageBox.information(d, "Déplacement impossible", "Un dossier ne peut pas être déplacé dans lui-même ou dans l’un de ses sous-dossiers.")
                    return
                except ValueError:
                    pass
            result["folder"] = dest
            d.accept()
        okb.clicked.connect(accept_dest); cb.clicked.connect(d.reject)
        folders.itemDoubleClicked.connect(lambda *_: accept_dest())
        if d.exec() != QDialog.DialogCode.Accepted:
            return None
        return result["folder"]

    def move_selected():
        item = tree.currentItem()
        if item is None or item.parent() is None:
            return
        path = item_path(item)
        if is_native_library_path(path, root):
            return
        dest_folder = choose_destination(path)
        if dest_folder is None:
            return
        if path.parent == dest_folder:
            return
        if is_native_library_path(dest_folder, root):
            QMessageBox.information(dialog, t("Modèle natif G-Skol"), t("Le dossier des modèles natifs G-Skol est protégé."))
            return
        target = dest_folder / path.name
        if target.exists():
            QMessageBox.information(dialog, "Déplacement impossible", "Un élément du même nom existe déjà dans le dossier de destination.")
            return
        try:
            shutil.move(str(path), str(target))
        except OSError as exc:
            QMessageBox.critical(dialog, "Déplacement impossible", str(exc))
            return
        populate(target)

    def delete_selected():
        item = tree.currentItem()
        if item is None or item.parent() is None:
            return
        path = item_path(item)
        if is_native_library_path(path, root):
            return
        kind = item_kind(item)
        if kind == "folder":
            text = f"Supprimer le dossier « {path.name} » ?"
            try:
                non_empty = any(path.iterdir())
            except OSError:
                non_empty = False
            if non_empty:
                text += "\n\nATTENTION : tous les sous-dossiers et modèles qu’il contient seront également supprimés."
        else:
            text = f"Supprimer définitivement le modèle « {path.stem} » ?"
        box = QMessageBox(dialog)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("Confirmer la suppression")
        box.setText(text)
        delete_action = box.addButton("Supprimer", QMessageBox.ButtonRole.DestructiveRole)
        cancel_action = box.addButton("Annuler", QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(cancel_action)
        box.exec()
        if box.clickedButton() is not delete_action:
            return
        parent_path = path.parent
        try:
            if kind == "folder":
                shutil.rmtree(path)
            else:
                path.unlink()
        except OSError as exc:
            QMessageBox.critical(dialog, "Suppression impossible", str(exc))
            return
        populate(parent_path if parent_path.exists() else root)

    result = {"path": None}
    def accept_item(item=None):
        item = item or tree.currentItem()
        if item is None:
            return
        if item_kind(item) == "folder":
            item.setExpanded(not item.isExpanded())
            return
        result["path"] = item_path(item)
        dialog.accept()

    tree.currentItemChanged.connect(update_buttons)
    tree.itemDoubleClicked.connect(lambda item, _col: accept_item(item))
    new_folder_btn.clicked.connect(create_folder)
    rename_btn.clicked.connect(rename_selected)
    move_btn.clicked.connect(move_selected)
    delete_btn.clicked.connect(delete_selected)
    open_btn.clicked.connect(lambda: accept_item())
    cancel_btn.clicked.connect(dialog.reject)

    populate(root)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return None
    return result["path"]


def resolve_model_fields(parent, envelope: dict, model_manager, collection_id: int, kind: str):
    """Applique un modèle graphique aux vrais champs de la collection courante.

    11.7.70.26.12 : la collection courante est la SOURCE métier ; le modèle de
    bibliothèque fournit uniquement des emplacements graphiques. Aucun champ métier
    n'est créé ici et aucune propriété métier de la collection n'est remplacée.
    """
    from core.field_catalog import FIELD_BY_KEY
    from core.model_library import collect_model_field_keys, remap_model_payload

    def _language():
        widget = parent
        while widget is not None:
            value = getattr(widget, "language", None)
            if value:
                return str(value)
            try:
                widget = widget.parentWidget()
            except Exception:
                break
        return "fr"

    language = _language()
    def t(text: str) -> str:
        return tr(text, language)

    def t_detection(text: str) -> str:
        # Le diagnostic lui-même peut contenir « — ». Ne jamais le découper sur
        # tous les tirets : on ne sépare que l'éventuel suffixe de relation MM3.
        # Les noms de champs utilisateur placés après « Relié à : » restent intacts.
        value = str(text or "")
        relation = ""
        marker = " — Relié à : "
        if marker in value:
            base, field_name = value.rsplit(marker, 1)
            relation = " — " + t("Relié à :") + " " + field_name
        elif value.endswith(" — Maître"):
            base = value[:-len(" — Maître")]
            relation = " — " + t("Maître")
        else:
            base = value
        return t(base) + relation

    def relation_suffix(cur: dict) -> str:
        relation = str(cur.get("relation") or "")
        if not relation:
            return ""
        if relation == "Maître":
            return " — " + t("Maître")
        if relation.startswith("Relié à : " ):
            return " — " + t("Relié à :") + " " + relation[len("Relié à : " ):]
        return " — " + relation

    def fr_type(value: str) -> str:
        key = str(value or "text").strip().casefold()
        label = {"text":"Texte","numeric":"Nombre","number":"Nombre","date":"Date",
                "boolean":"Bouton On / Off","bool":"Bouton On / Off","list":"Liste / Référentiel",
                "reference":"Liste / Référentiel","referential":"Liste / Référentiel","link":"Lien",
                "currency":"Monétaire","calculated":"Calculé","photo":"Photo / Image",
                "image":"Photo / Image","binary":"Photo / Image"}.get(key, str(value or "Texte"))
        return t(label)

    def norm_type(value: str) -> str:
        key = str(value or "text").strip().casefold()
        return {"number":"numeric","bool":"boolean","reference":"list","referential":"list",
                "image":"photo","binary":"photo"}.get(key, key)

    payload = dict(envelope.get("payload") or {})
    manifest = dict(envelope.get("field_manifest") or {})
    model_keys = collect_model_field_keys(kind, payload)
    custom = model_manager.custom_field_map(int(collection_id))
    payload_labels = payload.get("labels") or {}
    if not isinstance(payload_labels, dict):
        payload_labels = {}

    # Vrais champs de la collection courante : c'est EUX que l'utilisateur doit
    # voir ligne par ligne. Le modèle ouvert n'est que la destination graphique.
    try:
        visible_now = set(model_manager.visible_fields(int(collection_id)))
        # Un set rendait l'ordre du tableau aléatoire à chaque ouverture. On suit
        # désormais l'ordre de tabulation réel de la collection, puis les rares
        # champs visibles qui n'y figureraient pas encore.
        fallback_order = list(model_manager.all_model_keys(int(collection_id)))
        ordered_now = list(model_manager.tab_order(int(collection_id), fallback_order))
        current_keys = [k for k in ordered_now if k in visible_now]
        current_keys.extend(k for k in fallback_order if k in visible_now and k not in current_keys)
        # 11.7.70.26.76 — le numéro de fiche est un champ système MM3 :
        # il est toujours présent et géré automatiquement. Il ne doit donc pas
        # apparaître dans la correspondance utilisateur. On le conserve toutefois
        # dans le modèle/mapping interne afin que les vues Tableau gardent leur
        # colonne N° sans perturber la reconnaissance des autres champs.
        current_keys = [k for k in current_keys if str(k) != "record_number"]
    except Exception:
        current_keys = []

    current = []
    for key in current_keys:
        if key in custom:
            info = dict(custom[key])
            label = str(info.get("label") or key)
            ftype = str(info.get("field_type") or "text")
        else:
            spec = FIELD_BY_KEY.get(key)
            if spec is None:
                continue
            label = str(getattr(spec, "label", key))
            ftype = str(getattr(spec, "field_type", "text"))
        current.append({"key":str(key), "label":label, "field_type":ftype})

    # Deux clés MM3 différentes peuvent porter le même libellé (par exemple le
    # N° technique et un ancien champ N° importé). On conserve les deux champs,
    # mais on les rend explicitement distinguables dans le tableau.
    label_counts = {}
    for info in current:
        folded = info["label"].strip().casefold()
        label_counts[folded] = label_counts.get(folded, 0) + 1
    for info in current:
        if label_counts.get(info["label"].strip().casefold(), 0) > 1:
            if info["key"] == "record_number":
                info["display_label"] = info["label"] + " (fiche MM3)"
            elif info["key"] == "record_state":
                info["display_label"] = info["label"] + " (état MM3)"
            else:
                info["display_label"] = info["label"] + " (champ collection)"
        else:
            info["display_label"] = info["label"]

    # Les relations appartiennent à la collection, jamais au modèle graphique.
    try:
        current_masters = {str(k) for k in model_manager.field_masters(int(collection_id))}
    except Exception:
        current_masters = set()
    try:
        current_links = {str(k): str(v) for k, v in (model_manager.field_links(int(collection_id)) or {}).items()}
    except Exception:
        current_links = {}
    for info in current:
        key = info["key"]
        if key in current_masters:
            info["relation"] = "Maître"
        elif key in current_links:
            info["relation"] = "Relié à : " + next((x["label"] for x in current if x["key"] == current_links[key]), current_links[key])
        else:
            info["relation"] = ""

    def norm_label(value: str) -> str:
        txt = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode("ascii").casefold()
        return "".join(ch for ch in txt if ch.isalnum())

    model_slots = []
    for skey in model_keys:
        meta = dict(manifest.get(skey) or {})
        spec = FIELD_BY_KEY.get(skey)
        label = str(meta.get("label") or payload_labels.get(skey) or
                    (getattr(spec, "label", "") if spec else "") or skey)
        ftype = str(meta.get("field_type") or
                    (getattr(spec, "field_type", None) if spec else None) or "text")
        model_slots.append({"key":str(skey), "label":label, "field_type":ftype})

    by_model_key = {x["key"]: x for x in model_slots}
    by_model_label = {x["label"].strip().casefold(): x for x in model_slots if x["label"].strip()}

    rows=[]
    for cur in current:
        dest=None; detection="Aucun emplacement proposé — le champ restera dans la palette"
        # 11.7.70.26.15 — un modèle de Fiche est COSMÉTIQUE. Son type historique
        # ne doit jamais empêcher de reconnaître le vrai champ métier de la collection.
        # Exemple : Département peut être Texte dans un ancien modèle mais Liste dans
        # la collection importée ; Prix peut être numeric dans le modèle et Monétaire
        # dans la collection. Le champ de collection garde toujours son vrai type.
        exact=by_model_key.get(cur["key"])
        if exact:
            dest=exact
            detection=("Clé et type identiques reconnus" if norm_type(exact["field_type"]) == norm_type(cur["field_type"])
                       else "Clé identique reconnue — type métier de la collection conservé")
        else:
            exact=by_model_label.get(cur["label"].strip().casefold())
            if exact:
                dest=exact
                detection=("Libellé et type compatibles reconnus" if norm_type(exact["field_type"]) == norm_type(cur["field_type"])
                           else "Libellé identique reconnu — type métier de la collection conservé")
            else:
                aliases = {"site1":"site", "site":"site1", "epoque":"epoqueserie", "epoqueserie":"epoque", "classemineraux":"classe", "localitetype":"tl", "nom":"espece"}
                wanted = aliases.get(norm_label(cur["label"]), norm_label(cur["label"]))
                candidates = [slot for slot in model_slots if norm_label(slot["label"]) == wanted]
                if len(candidates) == 1:
                    dest=candidates[0]; detection="Libellé compatible reconnu — type métier de la collection conservé"
        if cur.get("relation"):
            detection += " — " + cur["relation"]
        rows.append((cur,dest,detection))

    # 11.7.70.26.69 — la correspondance d'un modèle d'échange doit être
    # immédiatement lisible : champs de la collection classés A → Z,
    # indépendamment de leur ordre graphique/tabulation dans le modèle source.
    rows.sort(key=lambda entry: str(entry[0].get("display_label", entry[0].get("label", ""))).casefold())

    # Si tout est identique, pas besoin d'interrompre l'utilisateur.
    if rows and all(dest is not None for _,dest,_ in rows) and len(rows) == len(model_slots):
        mapping={slot["key"]: None for slot in model_slots}
        for cur,dest,_ in rows:
            mapping[dest["key"]]=cur["key"]
        return remap_model_payload(kind, payload, mapping)

    dlg=QDialog(parent); dlg.setWindowTitle(t("Correspondance des champs du modèle")); dlg.setModal(True)
    dlg.resize(1180, max(540,min(820,315+34*len(rows))))
    root=QVBoxLayout(dlg); root.setContentsMargins(18,16,18,16); root.setSpacing(10)
    title=QLabel(t("Correspondance des champs du modèle")); title.setStyleSheet("font-size:20px; font-weight:800;"); root.addWidget(title)
    info=QLabel("Les champs du modèle servent uniquement de correspondances graphiques. Les types de la collection peuvent être proposés ici ; toute conversion sera vérifiée et confirmée, sans modifier le modèle source.")
    info.setWordWrap(True); root.addWidget(info)

    table=QTableWidget(len(rows),6)
    table.setHorizontalHeaderLabels([t("Action"),t("Champ de la collection"),t("Type collection"),t("Emplacement du modèle"),t("Type modèle"),t("Détection G-Skol")])
    table.verticalHeader().setVisible(True); table.setAlternatingRowColors(True)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    header=table.horizontalHeader()
    for col in range(6): header.setSectionResizeMode(col,QHeaderView.ResizeMode.Interactive)
    for col,w in enumerate((120,210,155,230,155,280)): table.setColumnWidth(col,w)
    table.setUpdatesEnabled(False)
    widgets=[]
    for row,(cur,dest,detection) in enumerate(rows):
        action=WheelOnlyWhenOpenComboBox(); action.addItem(t("Importer"), "Importer"); action.addItem(t("Créer"), "Créer"); action.addItem(t("Ne pas importer"), "Ne pas importer"); action.setCurrentIndex(action.findData("Importer" if dest else "Créer"))
        # 11.7.70.26.17 — État de la fiche est un champ SYSTEME MM3 unique.
        # On n'importe jamais une occurrence source comme champ graphique : le
        # slot natif du modèle est conservé séparément. Les valeurs du référentiel
        # sont gérées par la collection (OK / À vérifier / Libre + valeurs propres).
        if cur["key"] == "record_state" or (cur["key"] != "record_state" and norm_label(cur["label"]) == norm_label("État de la fiche")):
            action.setCurrentIndex(action.findData("Ne pas importer"))
            action.setEnabled(False)
            detection = "Champ système MM3 — non importé (valeurs de la collection conservées)"
        table.setCellWidget(row,0,action)
        item=QTableWidgetItem(cur.get("display_label", cur["label"])); item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable); table.setItem(row,1,item)
        type_combo=WheelOnlyWhenOpenComboBox()
        for type_key in ("text", "numeric", "currency", "date", "boolean", "list", "link", "calculated", "photo"):
            type_combo.addItem(fr_type(type_key), type_key)
        type_combo.setCurrentIndex(max(0, type_combo.findData(norm_type(cur["field_type"]))))
        if cur["key"] in ("record_state", "record_number", "photo_data"):
            type_combo.setEnabled(False)
        table.setCellWidget(row,2,type_combo)
        combo=WheelOnlyWhenOpenComboBox(); combo.addItem("---",None)
        # Brique 2.3.17 : afficher TOUS les emplacements réels du modèle
        # sélectionné, sans filtrage sur le type du champ de la collection.
        # Le type métier de la collection est conservé lors de l'application ;
        # l'utilisateur décide de la correspondance, même si les types historiques
        # du modèle diffèrent (cas fréquent des anciens modèles G-Skol).
        for slot in sorted(model_slots, key=lambda item: (str(item.get("label", "")).casefold(), str(item["key"]))):
            combo.addItem(slot["label"], slot["key"])
        if dest:
            idx=combo.findData(dest["key"]); combo.setCurrentIndex(idx if idx>=0 else 0)
        else: combo.setCurrentIndex(0)
        combo.setEnabled(action.currentData()=="Importer"); table.setCellWidget(row,3,combo)
        mt=QTableWidgetItem(fr_type(dest["field_type"]) if dest else "---"); mt.setFlags(mt.flags() & ~Qt.ItemFlag.ItemIsEditable); table.setItem(row,4,mt)
        det=QTableWidgetItem(t_detection(detection)); det.setFlags(det.flags() & ~Qt.ItemFlag.ItemIsEditable); table.setItem(row,5,det)
        rd={"cur":cur,"action":action,"combo":combo,"type":mt,"type_combo":type_combo,"det":det,"auto":dest}
        widgets.append(rd)
        def refresh(_=None,rd=rd):
            action_text=rd["action"].currentData(); importing=action_text=="Importer"; rd["combo"].setEnabled(importing)
            if action_text == "Créer":
                rd["type"].setText(fr_type(rd["cur"]["field_type"]))
                suffix = relation_suffix(rd["cur"])
                rd["det"].setText(t("Ajout à la palette — à placer par l'utilisateur") + suffix); return
            if not importing:
                rd["type"].setText("---"); rd["det"].setText(t("Champ conservé dans la collection — non ajouté au modèle")); return
            key=rd["combo"].currentData(); slot=by_model_key.get(str(key)) if key else None
            rd["type"].setText(fr_type(slot["field_type"]) if slot else "---")
            if not slot: rd["det"].setText(t("Choisissez un emplacement du modèle"))
            elif rd["auto"] and slot["key"]==rd["auto"]["key"]: rd["det"].setText(t_detection(detection))
            else: rd["det"].setText(t("Correspondance choisie par l'utilisateur"))
        action.currentTextChanged.connect(refresh); combo.currentIndexChanged.connect(refresh)
        def selected_destination(_index, rd=rd):
            if rd["combo"].currentData() is not None and rd["action"].currentData() == "Créer":
                rd["action"].setCurrentIndex(rd["action"].findData("Importer"))
        combo.currentIndexChanged.connect(selected_destination)
    table.setUpdatesEnabled(True); root.addWidget(table,1)

    foot=QHBoxLayout(); all_import=QPushButton(t("Tout importer")); all_ignore=QPushButton(t("Tout ignorer"))
    foot.addWidget(all_import); foot.addWidget(all_ignore); foot.addStretch(1)
    cancel=QPushButton(t("Annuler")); ok=QPushButton(t("Valider la correspondance")); foot.addWidget(cancel); foot.addWidget(ok); root.addLayout(foot)
    def set_all_import():
        for rd in widgets:
            rd["action"].setCurrentIndex(rd["action"].findData("Importer" if rd["combo"].currentData() is not None else "Créer"))
    all_import.clicked.connect(set_all_import); all_ignore.clicked.connect(lambda:[rd["action"].setCurrentIndex(rd["action"].findData("Ne pas importer")) for rd in widgets])
    cancel.clicked.connect(dlg.reject)

    # 11.7.70.26.16 — valider AVANT de fermer la fenêtre. En cas de doublon ou
    # de correspondance incomplète, l'utilisateur reste exactement dans son tableau
    # avec toutes ses sélections. Le message donne les numéros de lignes concernés.
    def validate_and_accept():
        # Ne jamais convertir implicitement les données métier ou les liens.
        # Les changements de type sont possibles dans l'Atelier des champs, où
        # les outils d'analyse de conversion et les confirmations existent déjà.
        changed = [(i, rd) for i, rd in enumerate(widgets, 1)
                   if norm_type(rd["type_combo"].currentData()) != norm_type(rd["cur"]["field_type"])]
        if changed:
            details = "\n".join(f"Ligne {i} : {rd['cur']['label']} — {fr_type(rd['cur']['field_type'])} → {fr_type(rd['type_combo'].currentData())}" for i, rd in changed[:8])
            QMessageBox.warning(dlg, "Conversion de type à confirmer dans l'Atelier",
                "La correspondance ne peut pas convertir silencieusement les données ou les référentiels.\n"
                "Effectuez d'abord ces conversions dans l'Atelier des champs de la collection, "
                "puis rouvrez ce tableau :\n\n" + details)
            return
        used = {}
        for row_no, rd in enumerate(widgets, start=1):
            if rd["action"].currentData() != "Importer":
                continue
            skey = rd["combo"].currentData()
            if not skey:
                QMessageBox.warning(dlg, "Correspondance incomplète",
                    f"Ligne {row_no} : choisissez un emplacement du modèle pour « {rd['cur']['label']} », "
                    "ou sélectionnez « Créer » / « Ne pas importer ».")
                table.scrollToItem(table.item(row_no-1, 1)); table.selectRow(row_no-1)
                return
            skey = str(skey)
            used.setdefault(skey, []).append(row_no)
        duplicates = [(key, lines) for key, lines in used.items() if len(lines) > 1]
        if duplicates:
            key, lines = duplicates[0]
            label = by_model_key.get(key, {}).get("label", key)
            line_text = " et ".join(str(n) for n in lines)
            QMessageBox.warning(dlg, "Emplacement déjà utilisé",
                f"L'emplacement « {label} » a été choisi pour plusieurs champs (lignes {line_text}). "
                "Choisissez un emplacement différent.")
            table.scrollToItem(table.item(lines[0]-1, 1)); table.selectRow(lines[0]-1)
            return
        dlg.accept()

    ok.clicked.connect(validate_and_accept)
    if QApplication.overrideCursor() is not None: QApplication.restoreOverrideCursor()
    QApplication.processEvents()
    if dlg.exec()!=QDialog.DialogCode.Accepted: return None

    QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor); QApplication.processEvents()
    try:
        mapping={slot["key"]:None for slot in model_slots}
        # Le champ système natif doit survivre même si sa ligne source est forcée
        # sur « Ne pas importer ». Cela empêche à la fois sa disparition et la
        # création d'un second État de la fiche dans le bandeau.
        if "record_state" in mapping:
            mapping["record_state"] = "record_state"
        # Le N° système n'est plus affiché dans la boîte de correspondance, mais
        # reste relié à lui-même en interne. Il demeure ainsi disponible dans les
        # modèles de Tableau et dans la Fiche sans intervention de l'utilisateur.
        if "record_number" in mapping:
            mapping["record_number"] = "record_number"
        palette_keys=[]
        for rd in widgets:
            if rd["action"].currentData()=="Créer":
                palette_keys.append(rd["cur"]["key"]); continue
            if rd["action"].currentData()!="Importer": continue
            skey=str(rd["combo"].currentData())
            mapping[skey]=rd["cur"]["key"]
        result = remap_model_payload(kind,payload,mapping)
        # « Créer » signifie ici créer une entrée de PALETTE, pas un champ métier
        # et pas une zone graphique. Le champ existe déjà dans la collection.
        vis = dict(result.get("visible") or {})
        for key in palette_keys:
            vis.setdefault(str(key), False)
        result["visible"] = vis
        # 11.7.70.26.22 — la palette de l’Atelier doit continuer à représenter
        # TOUTE la collection, pas seulement les emplacements graphiques du modèle
        # importé. _apply_history_state() masque volontairement toute ligne absente
        # de field_keys ; c’était la raison exacte pour laquelle fermer/réouvrir
        # l’Atelier faisait réapparaître les champs. Conserver ici toutes les clés
        # métier de la collection, y compris celles choisies « Créer » ou
        # « Ne pas importer ». Elles restent décochées si elles ne sont pas placées.
        field_keys = [str(info["key"]) for info in current]
        for technical_key in ("record_number", "record_state", "photo_data"):
            if technical_key in model_keys and technical_key not in field_keys:
                field_keys.append(technical_key)
        result["field_keys"] = field_keys
        # Le modèle ne possède aucune autorité sur les relations métier.
        result["field_masters"] = sorted(current_masters)
        result["field_links"] = dict(current_links)
        # Un modèle de Fiche transporte une présentation, jamais les libellés métier
        # de la collection qui le reçoit. Conserver explicitement les libellés réels
        # évite qu’une clé technique custom_xxx devienne visible dans la palette.
        result["labels"] = {str(info["key"]): str(info["label"]) for info in current}
        return result
    finally:
        QApplication.restoreOverrideCursor()

