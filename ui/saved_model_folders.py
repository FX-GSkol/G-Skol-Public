"""Choix et gestion des dossiers de modèles enregistrés dans une collection."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QTreeWidget, QTreeWidgetItem, QInputDialog, QMessageBox, QComboBox, QLabel, QDialogButtonBox)
from core import saved_model_folders as store
from core.i18n import tr


def choose_folder(parent, db, cid, kind, current='', exclude=()):
    excluded=tuple(str(path).casefold() for path in exclude)
    def available(path):
        value=str(path).casefold()
        return not any(value==blocked or value.startswith(blocked+'/') for blocked in excluded)
    options=['(Sans dossier)']+[path for path in store.folders(db,cid,kind) if available(path)]+['+ Nouveau dossier ou sous-dossier…']
    index=options.index(current) if current in options else 0
    value,ok=QInputDialog.getItem(parent,'Dossier du modèle','Enregistrer dans :',options,index,False)
    if not ok: return None
    if value == options[-1]:
        value,ok=QInputDialog.getText(parent,'Nouveau dossier','Chemin du dossier (ex. Région / Année) :')
        if not ok: return None
        try:
            value=store.normalize(value)
            if not value: raise ValueError('Saisissez un nom de dossier.')
            if not available(value): raise ValueError('Ce dossier est réservé à l’autre type d’état.')
            store.create_folder(db,cid,kind,value)
        except ValueError as exc:
            QMessageBox.warning(parent,'Dossier invalide',str(exc));return None
    return '' if value==options[0] else value


class FolderDialog(QDialog):
    def __init__(self,parent,db,cid,kind,items,on_change):
        super().__init__(parent)
        self.db,self.cid,self.kind,self.items,self.on_change=db,cid,kind,items,on_change
        self.setWindowTitle('Dossiers de la collection')
        self.resize(570,480)
        layout=QVBoxLayout(self)
        self.tree=QTreeWidget()
        self.tree.setHeaderLabel('Dossiers et modèles enregistrés')
        layout.addWidget(self.tree)
        row=QHBoxLayout();layout.addLayout(row)
        for label,action in [('+ Dossier',self.add_folder),('Renommer dossier',self.rename_folder),('Supprimer dossier',self.remove_folder),('Déplacer le modèle',self.move_item),('Fermer',self.accept)]:
            btn=QPushButton(label);btn.clicked.connect(action);row.addWidget(btn)
        self.refresh()

    def selection(self):
        item=self.tree.currentItem()
        return item.data(0,Qt.ItemDataRole.UserRole) if item else None

    def refresh(self):
        self.tree.clear()
        root=QTreeWidgetItem(self.tree,['📁 Sans dossier'])
        root.setData(0,Qt.ItemDataRole.UserRole,('folder',''))
        nodes={'':root}
        for path in store.folders(self.db,self.cid,self.kind):
            parent=nodes.get(path.rpartition('/')[0],root)
            node=QTreeWidgetItem(parent,['📁 '+path.rpartition('/')[2]])
            node.setData(0,Qt.ItemDataRole.UserRole,('folder',path))
            nodes[path]=node
        for name in sorted(self.items,key=str.casefold):
            folder=store.folder_for(self.db,self.cid,self.kind,name)
            node=QTreeWidgetItem(nodes.get(folder,root),['📄 '+name])
            node.setData(0,Qt.ItemDataRole.UserRole,('item',name))
        self.tree.expandAll()
        self.on_change()

    def add_folder(self):
        selected=self.selection()
        parent=selected[1] if selected and selected[0]=='folder' else ''
        name,ok=QInputDialog.getText(self,'Nouveau dossier','Nom du dossier ou sous-dossier :')
        if not ok:return
        try:
            path=store.normalize('/'.join(filter(None,(parent,name))))
            if not path:raise ValueError('Saisissez un nom de dossier.')
            store.create_folder(self.db,self.cid,self.kind,path)
            self.refresh()
        except ValueError as exc:QMessageBox.warning(self,'Dossier invalide',str(exc))

    def rename_folder(self):
        selected=self.selection()
        if not selected or selected[0]!='folder' or not selected[1]:return
        old=selected[1]
        value,ok=QInputDialog.getText(self,'Renommer le dossier','Nouveau nom :',text=old.rpartition('/')[2])
        if not ok:return
        try:
            value=store.normalize(value)
            if '/' in value or not value:raise ValueError('Saisissez un seul nom de dossier.')
            store.rename_folder(self.db,self.cid,self.kind,old,'/'.join(filter(None,(old.rpartition('/')[0],value))))
            self.refresh()
        except ValueError as exc:QMessageBox.warning(self,'Renommage impossible',str(exc))

    def remove_folder(self):
        selected=self.selection()
        if not selected or selected[0]!='folder' or not selected[1]:return
        if QMessageBox.question(self,'Supprimer le dossier',f'Supprimer « {selected[1]} » et ses sous-dossiers vides ?',QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.No)!=QMessageBox.StandardButton.Yes:return
        try:store.remove_folder(self.db,self.cid,self.kind,selected[1]);self.refresh()
        except ValueError as exc:QMessageBox.warning(self,'Suppression impossible',str(exc))

    def move_item(self):
        selected=self.selection()
        if not selected or selected[0]!='item':return
        name=selected[1]
        folder=choose_folder(self,self.db,self.cid,self.kind,store.folder_for(self.db,self.cid,self.kind,name))
        if folder is None:return
        store.assign(self.db,self.cid,self.kind,name,folder)
        self.refresh()


def manage_folders(parent,db,cid,kind,items,on_change):
    FolderDialog(parent,db,cid,kind,items,on_change).exec()


class SavedModelCombo(QComboBox):
    """Liste de modèles avec dossiers repliables, sans modifier la sélection en ouvrant un dossier."""
    def __init__(self, parent, db_path, collection_id, kind, models):
        super().__init__(parent)
        self._db_path = db_path
        self._collection_id = collection_id
        self._kind = kind
        self._models = models

    def showPopup(self):
        db = self._db_path()
        cid = int(self._collection_id())
        models = self._models()
        dialog = QDialog(self)
        language = getattr(getattr(self.parent(), 'startup', None), 'settings', None)
        language = getattr(language, 'language', None) or getattr(self.parent(), 'language', 'fr')
        dialog.setWindowTitle(tr('Ouvrir une requête enregistrée' if self._kind == 'requete' else 'Ouvrir une vue enregistrée', language))
        dialog.resize(570, 470)
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel(tr('Ouvrez un dossier, puis double-cliquez sur la sauvegarde.', language)))
        tree = QTreeWidget(dialog)
        tree.setHeaderLabel(tr('Dossiers et sauvegardes de cette collection', language))
        tree.setExpandsOnDoubleClick(False)
        layout.addWidget(tree)
        nodes = {}
        fresh = QTreeWidgetItem(tree, [tr('— Nouvelle requête —' if self._kind == 'requete' else '— Vue actuelle —', language)])
        fresh.setData(0, Qt.ItemDataRole.UserRole, '__mm3_fresh__')
        root = QTreeWidgetItem(tree, ['📁 ' + tr('Sans dossier', language)])
        root.setData(0, Qt.ItemDataRole.UserRole, None)
        nodes[''] = root
        paths = set(store.folders(db, cid, self._kind))
        for name in models:
            path = store.folder_for(db, cid, self._kind, name)
            while path:
                paths.add(path)
                path = path.rpartition('/')[0]
        for path in sorted(paths, key=lambda p: (p.count('/'), p.casefold())):
            node = QTreeWidgetItem(nodes.get(path.rpartition('/')[0], root), ['📁 ' + path.rpartition('/')[2]])
            node.setData(0, Qt.ItemDataRole.UserRole, None)
            nodes[path] = node
        current = self.currentData()
        current_item = None
        for name in sorted(models, key=str.casefold):
            folder = store.folder_for(db, cid, self._kind, name)
            item = QTreeWidgetItem(nodes.get(folder, root), ['📄 ' + str(name)])
            item.setData(0, Qt.ItemDataRole.UserRole, str(name))
            if str(name) == current:
                current_item = item
        root.setExpanded(True)
        if current_item is not None:
            tree.setCurrentItem(current_item)
            parent = current_item.parent()
            while parent is not None:
                parent.setExpanded(True)
                parent = parent.parent()
        def select_item(item):
            if item is None: return
            name = item.data(0, Qt.ItemDataRole.UserRole)
            if name in models or name == '__mm3_fresh__': dialog.accept()
            else: item.setExpanded(not item.isExpanded())
        tree.itemDoubleClicked.connect(lambda item, _column: select_item(item))
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Open | QDialogButtonBox.StandardButton.Cancel, parent=dialog)
        buttons.button(QDialogButtonBox.StandardButton.Open).setText('Ouvrir')
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText('Annuler')
        buttons.accepted.connect(lambda: select_item(tree.currentItem()))
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            item = tree.currentItem()
            name = item.data(0, Qt.ItemDataRole.UserRole) if item is not None else None
            index = 0 if name == '__mm3_fresh__' else self.findData(name)
            if index >= 0 and (name in models or name == '__mm3_fresh__'):
                self.setCurrentIndex(index)
