import json

from PyQt5.QtWidgets import QItemDelegate, QComboBox
from PyQt5.QtCore import Qt

d = json.JSONDecoder()
f = open("/usr/share/iso-codes/json/iso_639-3.json", "r")
iso639_3 = d.decode(f.read())["639-3"]
LANGUAGES = {lang["alpha_3"]: lang["name"] for lang in iso639_3}
f.close()
del f


class LanguageDelegate(QItemDelegate):
    def createEditor(self, parent, option, index):
        editor = QComboBox(parent)

        editor.addItem("Unknown (und)", None)
        editor.insertSeparator(editor.count())

        common_langs = ["eng", "deu", "ita", "spa", "fra", "por", "nld",
                        "swe", "nor", "fin", "pol", "ron", "rus", "tur",
                        "vie", "kor", "arz", "pes", "hin", "zho", "jpn"]

        for key in common_langs:
            lang = LANGUAGES[key]
            editor.addItem(f"{lang} ({key})", key)

        editor.insertSeparator(editor.count())

        for key, lang in sorted(LANGUAGES.items(), key=lambda item: item[1]):
            if key in common_langs:
                continue
            editor.addItem(f"{lang} ({key})", key)

        return editor

    def setEditorData(self, editor, index):
        value = index.data(Qt.EditRole)
        langindex = editor.findData(value)

        if langindex >= 0:
            editor.setCurrentIndex(langindex)
        else:
            editor.setCurrentIndex(0)

    def setModelData(self, editor, model, index):
        model.setData(index, editor.currentData(), Qt.EditRole)

    def updateEditorGeometry(self, editor, option, index):
        editor.setGeometry(option.rect)
