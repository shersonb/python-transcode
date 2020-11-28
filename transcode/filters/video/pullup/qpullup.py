from PyQt5.QtGui import (QColor, QValidator)
from PyQt5.QtCore import Qt, QRegExp
from PyQt5.QtWidgets import (QItemDelegate, QLineEdit, QAction, QMessageBox,
                             QVBoxLayout, QHBoxLayout, QLabel)
from PyQt5.QtCore import pyqtSignal, pyqtSlot
from PyQt5.QtGui import QRegExpValidator
from fractions import Fraction as QQ
import regex
from functools import partial

from . import Zone
from transcode.pyqtgui.qzones import ZoneDlg, BaseShadowZone
from transcode.pyqtgui.qframetablecolumn import ZoneCol


class PatternValidator(QValidator):
    def validate(self, string, offset):
        value = string.upper()

        if len(string) == 0:
            return QValidator.Acceptable, value, offset

        if len(string) == 1:
            return QValidator.Intermediate, value, offset

        if not regex.match(r"^[A-Z\*]+$", value):
            return QValidator.Invalid, value, offset

        if value is not None:
            value = value.upper()

            if "A" not in value[:2]:
                return QValidator.Invalid, value, offset

            evens = value[::2]
            evens_start = min(evens.replace("*", ""))
            evens_end = max(evens.replace("*", ""))

            odds = value[1::2]
            odds_start = min(odds.replace("*", ""))
            odds_end = max(odds.replace("*", ""))

            old_blksize = len(value)//2
            new_blksize = min(ord(evens_end) - ord(evens_start) +
                              1, ord(odds_end) - ord(odds_start) + 1)

            for char in range(ord(evens_start), ord(evens_start) + new_blksize):
                if chr(char) not in evens:
                    return QValidator.Invalid, value, offset

            for char in range(ord(odds_start), ord(odds_start) + new_blksize):
                if chr(char) not in odds:
                    return QValidator.Invalid, value, offset

            if len(value) % 2:
                return QValidator.Intermediate, value, offset

        return QValidator.Acceptable, value, offset


class ShadowZone(BaseShadowZone, Zone):
    def __init__(self, zone):
        self.yblend = None
        self.uvblend = None
        super().__init__(zone)


class QPullup(ZoneDlg):
    zonename = "Pullup Zone"
    title = "Pullup Zone Editor"
    shadowclass = ShadowZone

    def _prepare(self):
        self.pulldownLabel = QLabel("Pattern:", self)
        self.pulldownEdit = QLineEdit(self)
        self.pulldownValidator = PatternValidator(self)
        self.pulldownEdit.setValidator(self.pulldownValidator)
        self.pulldownEdit.textChanged.connect(self.patternChanged)

        layout = QVBoxLayout(self)
        self.setLayout(layout)

        self._prepareImageView()
        self._prepareStdZoneControls()

        sublayout = QHBoxLayout()
        sublayout.addWidget(self.pulldownLabel)
        sublayout.addWidget(self.pulldownEdit)
        sublayout.addStretch()

        layout.addLayout(sublayout)

        self._prepareDlgButtons(layout)

    def patternChanged(self, text):
        (valid, _, _) = self.pulldownValidator.validate(text, 0)

        if valid == 2:
            self.pulldown = text


class FrameRateDelegate(QItemDelegate):
    def createEditor(self, parent, option, index):
        regex = QRegExp(r"^(\d+(?:\.\d+)?|\.\d+|\d+/\d+)$")
        validator = QRegExpValidator(regex)
        editor = QLineEdit(parent)
        editor.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        editor.setValidator(validator)
        return editor

    def setEditorData(self, editor, index):
        value = index.model().data(index, Qt.EditRole)
        editor.setText(str(value))

    def setModelData(self, editor, model, index):
        value = editor.text()

        if regex.match("^\d+/\d+$", value):
            value = QQ(value)

        elif regex.match("^\d+$", value):
            value = int(value)

        else:
            value = float(value)

        model.setData(index, value, Qt.EditRole)

    def updateEditorGeometry(self, editor, option, index):
        editor.setGeometry(option.rect)


class OffsetDelegate(QItemDelegate):
    def createEditor(self, parent, option, index):
        regex = QRegExp(r"^\d+$")
        validator = QRegExpValidator(regex)
        editor = QLineEdit(parent)
        editor.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        editor.setValidator(validator)
        return editor

    def setEditorData(self, editor, index):
        value = index.model().data(index, Qt.EditRole)
        editor.setText(str(value))

    def setModelData(self, editor, model, index):
        value = int(editor.text())
        model.setData(index, value, Qt.EditRole)

    def updateEditorGeometry(self, editor, option, index):
        editor.setGeometry(option.rect)


class BaseFrameRateCol(ZoneCol):
    textalign = Qt.AlignRight | Qt.AlignVCenter
    bgcolor = QColor(128, 128, 255)
    bgcoloralt = QColor(255, 255, 255)
    fgcolor = QColor(0, 0, 0)
    fgcoloralt = QColor(160, 160, 160)

    @staticmethod
    def setZoneValues(table, zone, src_fps=QQ(24000, 1001), pulldown=None, pulldownoffset=0):
        zone.src_fps = src_fps
        zone.pulldown = pulldown
        zone.pulldownoffset = pulldownoffset
        table.contentsModified.emit()

    def createContextMenu(self, table, index, obj):
        menu = ZoneCol.createContextMenu(self, table, index, obj)
        menu.addSeparator()
        J, zone = self.filter.zoneAt(obj)

        menu.addAction(QAction("&AA (24000/1001)", table,
                               triggered=partial(self.setZoneValues, table=table, zone=zone)))
        menu.addAction(QAction("AA (&30000/1001)", table,
                               triggered=partial(self.setZoneValues, table=table, zone=zone, src_fps=QQ(30000, 1001))))
        menu.addAction(QAction("A&B (24000/1001)", table, triggered=partial(
            self.setZoneValues, table=table, zone=zone, pulldown="AB")))
        menu.addSeparator()
        menu.addAction(QAction("AAABBCCCDD(&0) (30000/1001)", table,
                               triggered=partial(self.setZoneValues, table=table, zone=zone, src_fps=QQ(30000, 1001),
                                                 pulldown="AAABBCCCDD", pulldownoffset=(zone.src_start - obj) % 5)))
        menu.addAction(QAction("AAABBCCCDD(&1) (30000/1001)", table,
                               triggered=partial(self.setZoneValues, table=table, zone=zone, src_fps=QQ(30000, 1001),
                                                 pulldown="AAABBCCCDD", pulldownoffset=(1 + zone.src_start - obj) % 5)))
        menu.addAction(QAction("AAABBCCCDD(&2) (30000/1001)", table,
                               triggered=partial(self.setZoneValues, table=table, zone=zone, src_fps=QQ(30000, 1001),
                                                 pulldown="AAABBCCCDD", pulldownoffset=(2 + zone.src_start - obj) % 5)))
        menu.addAction(QAction("AAABBCCCDD(&3) (30000/1001)", table,
                               triggered=partial(self.setZoneValues, table=table, zone=zone, src_fps=QQ(30000, 1001),
                                                 pulldown="AAABBCCCDD", pulldownoffset=(3 + zone.src_start - obj) % 5)))
        menu.addAction(QAction("AAABBCCCDD(&4) (30000/1001)", table,
                               triggered=partial(self.setZoneValues, table=table, zone=zone, src_fps=QQ(30000, 1001),
                                                 pulldown="AAABBCCCDD", pulldownoffset=(4 + zone.src_start - obj) % 5)))
        menu.addSeparator()
        menu.addAction(QAction("AAABBCC&DDD (30000/1001)", table,
                               triggered=partial(self.setZoneValues, table=table, zone=zone, src_fps=QQ(30000, 1001),
                                                 pulldown="AAABBCCDDD", pulldownoffset=0)))
        menu.addAction(QAction("AAABBCCDD&E (30000/1001)", table,
                               triggered=partial(self.setZoneValues, table=table, zone=zone, src_fps=QQ(30000, 1001),
                                                 pulldown="AAABBCCDDE", pulldownoffset=0)))
        menu.addSeparator()
        menu.addAction(QAction("Auto Frame Rate", table,
                               triggered=partial(self.autoFrameRate, table=table)))
        return menu

    def autoFrameRate(self, table):
        isdefault = len(self.filter) == 1 and self.filter.start.src_fps == QQ(
            24000, 1001) and self.filter.start.pulldown is None

        if isdefault or QMessageBox.question(table, "Auto Frame Rate",
                                             "Current zone settings will be lost! Do you wish to proceed?", QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            self.filter.autoframerate()
            table.contentsModified.emit()


class FrameRateCheckCol(BaseFrameRateCol):
    headerdisplay = "FRZ"
    width = 72
    flags = Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsUserCheckable

    def display(self, index, obj):
        K, zone = self.filter.zoneAt(obj)
        return "%s" % K

    def setcheckstate(self, index, obj, data):
        if obj == 0:
            return

        if self.checkstate(index, obj):
            self.filter.removeZoneAt(obj)

        else:
            self.filter.insertZoneAt(obj, src_fps=QQ(24000, 1001))


class YBlendCheckCol(BaseFrameRateCol):
    headerdisplay = "YB"
    display = ""
    width = 36

    def display(self, index, obj):
        return ""

    def checkstate(self, index, obj):
        K, zone = self.filter.zoneAt(obj)
        return zone.yblend

    def setcheckstate(self, index, obj, data):
        K, zone = self.filter.zoneAt(obj)

        if self.checkstate(index, obj):
            zone.yblend = False
            return True

        else:
            zone.yblend = True
            return True

    def flags(self, index, obj):
        K, zone = self.filter.zoneAt(obj)

        if zone.pulldown is not None and "A" in zone.pulldown[:2] and zone.dest_fps != zone.src_fps:
            return Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsUserCheckable

        return Qt.ItemIsSelectable | Qt.ItemIsUserCheckable


class UVBlendCheckCol(BaseFrameRateCol):
    headerdisplay = "UVB"
    display = ""
    width = 36

    def display(self, index, obj):
        return ""

    def checkstate(self, index, obj):
        K, zone = self.filter.zoneAt(obj)
        return zone.uvblend

    def setcheckstate(self, index, obj, data):
        K, zone = self.filter.zoneAt(obj)

        if self.checkstate(index, obj):
            zone.uvblend = False
            return True

        else:
            zone.uvblend = True
            return True

    def flags(self, index, obj):
        K, zone = self.filter.zoneAt(obj)

        if zone.pulldown is not None and "A" in zone.pulldown[:2] and zone.dest_fps != zone.src_fps:
            return Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsUserCheckable

        return Qt.ItemIsSelectable | Qt.ItemIsUserCheckable


class FrameRateCol(BaseFrameRateCol):
    itemdelegate = FrameRateDelegate()
    headerdisplay = "Frame Rate"
    width = 128
    checkstate = None

    def display(self, index, obj):
        K, zone = self.filter.zoneAt(obj)
        return str(zone.src_fps)

    def editdata(self, index, obj):
        K, zone = self.filter.zoneAt(obj)
        return zone.src_fps

    def seteditdata(self, index, obj, value):
        K, zone = self.filter.zoneAt(obj)

        if value is None:
            zone.src_fps = QQ(24000, 1001)

        else:
            zone.src_fps = value

    def flags(self, index, obj):
        K, zone = self.filter.zoneAt(obj)

        if zone.src_start == obj:
            return Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable

        return Qt.ItemIsEnabled | Qt.ItemIsSelectable


class TCPatternCol(BaseFrameRateCol):
    headerdisplay = "Pattern"
    width = 128
    checkstate = None

    def display(self, index, obj):
        K, zone = self.filter.zoneAt(obj)

        if zone.pulldown is None:
            return "AA"

        return zone.pulldown

    def editdata(self, index, obj):
        K, zone = self.filter.zoneAt(obj)

        if zone.pulldown is None:
            return "AA"

        return zone.pulldown

    def seteditdata(self, index, obj, value):
        K, zone = self.filter.zoneAt(obj)

        if value is None or value.upper() == "AA":
            zone.pulldown = None
            return True

        else:
            try:
                zone.pulldown = value

            except:
                return False

            return True

    def flags(self, index, obj):
        K, zone = self.filter.zoneAt(obj)

        if zone.src_start == obj:
            return Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable

        return Qt.ItemIsEnabled | Qt.ItemIsSelectable


class TCPatternOffsetCol(BaseFrameRateCol):
    headerdisplay = "Offset"
    itemdelegate = OffsetDelegate()
    width = 64
    checkstate = None

    def display(self, index, obj):
        K, zone = self.filter.zoneAt(obj)

        if zone.pulldown is None:
            return "-"

        return "%d" % ((obj - zone.prev_start + zone.pulldownoffset) % zone.old_blksize)

    def flags(self, index, obj):
        K, zone = self.filter.zoneAt(obj)
        return Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable

    def editdata(self, index, obj):
        K, zone = self.filter.zoneAt(obj)
        return zone.pulldownoffset

    def seteditdata(self, index, obj, value):
        if value is None:
            return False

        K, zone = self.filter.zoneAt(obj)

        if zone.pulldown is not None:
            zone.pulldownoffset = (
                value - (index - zone.prev_start)) % zone.old_blksize


class FrameRateECol(BaseFrameRateCol):
    headerdisplay = "E"
    width = 64
    flags = Qt.ItemIsEnabled | Qt.ItemIsSelectable
    checkstate = None

    def display(self, index, obj):
        m = self.filter.final_fields(obj)[0]

        if m < 0:
            return "-"

        return "%s" % m


class FrameRateOCol(BaseFrameRateCol):
    headerdisplay = "O"
    width = 64
    flags = Qt.ItemIsEnabled | Qt.ItemIsSelectable
    checkstate = None

    def display(self, index, obj):
        m = self.filter.final_fields(obj)[1]

        if m < 0:
            return "-"

        return "%s" % m
