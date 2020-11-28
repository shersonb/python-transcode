from PyQt5.QtCore import Qt, QRegExp
from PyQt5.QtWidgets import QDoubleSpinBox, QItemDelegate, QLineEdit
from PyQt5.QtGui import QRegExpValidator


class QHexLineEdit(QLineEdit):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        regex = QRegExp("(?:[0-9a-f]\s?){1,15}[0-9a-f]")
        regex.setCaseSensitivity(Qt.CaseInsensitive)
        self.setValidator(QRegExpValidator(regex))


class UIDDelegate(QItemDelegate):
    def createEditor(self, parent, option, index):
        editor = QHexLineEdit(parent)
        return editor

    def setEditorData(self, editor, index):
        editor.setText(index.data(Qt.DisplayRole))

    def setModelData(self, editor, model, index):
        model.setData(index, int(
            editor.text().replace(" ", ""), 16), Qt.EditRole)

    def updateEditorGeometry(self, editor, option, index):
        editor.setGeometry(option.rect)
