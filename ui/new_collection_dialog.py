from PySide6.QtWidgets import QDialog,QFormLayout,QLineEdit,QPlainTextEdit,QPushButton,QHBoxLayout,QVBoxLayout,QWidget
from PySide6.QtCore import Qt
from core.i18n import tr

class NewCollectionDialog(QDialog):
    def __init__(self,parent=None,language='fr'):
        super().__init__(parent)
        self.language=language or 'fr'
        self.setWindowTitle(tr("Nouvelle collection — Informations",self.language))
        self.name=QLineEdit()
        self.owner=QLineEdit()
        self.description=QPlainTextEdit()
        form=QFormLayout()
        form.addRow(tr("Nom :",self.language),self.name)
        form.addRow(tr("Propriétaire :",self.language),self.owner)
        form.addRow(tr("Description :",self.language),self.description)
        self.btn_create=QPushButton(tr("Créer",self.language))
        self.btn_cancel=QPushButton(tr("Annuler",self.language))
        self.btn_create.setEnabled(False)
        self.name.textChanged.connect(lambda t:self.btn_create.setEnabled(bool(t.strip())))
        self.btn_create.clicked.connect(self.accept)
        self.btn_cancel.clicked.connect(self.reject)
        buttons=QHBoxLayout();buttons.addStretch();buttons.addWidget(self.btn_create);buttons.addWidget(self.btn_cancel)
        lay=QVBoxLayout(self);lay.addLayout(form);lay.addLayout(buttons)
    def values(self):
        return {"name":self.name.text().strip(),"owner":self.owner.text().strip(),"description":self.description.toPlainText().strip()}
