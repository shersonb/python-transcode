from PyQt5.QtWidgets import QDoubleSpinBox
from PyQt5.QtCore import Qt, QRegExp
from PyQt5.QtGui import QRegExpValidator
import regex


class QTimeSelect(QDoubleSpinBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        regex = QRegExp("\d:\d{1,2}:\d{1,2}(?:\.\d{0,9})")
        regex.setCaseSensitivity(Qt.CaseInsensitive)
        self._validator = QRegExpValidator(regex)
        self.setDecimals(9)

    def validate(self, text, pos):
        return self._validator.validate(text, pos)

    def valueFromText(self, text):
        matches = regex.findall(r"^(\d+):(\d+):(\d+(?:\.\d*))$", text)

        if matches:
            (h, m, s), = matches
            return 3600*int(h) + 60*int(m) + float(s)

    def textFromValue(self, value):
        m, s = divmod(value, 60)
        h, m = divmod(int(m), 60)
        return f"{h}:{m:02d}:{s:012.9f}"

    def stepBy(self, dt):
        currentValue = self.value()
        currentText = self.text()
        currentPosition = self.lineEdit().cursorPosition()
        matches = regex.findall(r"^(\d+):(\d+):(\d+(?:\.\d*))$", currentText)

        if matches:
            (h, m, s), = matches

        if currentPosition <= len(h):
            self.setValue(currentValue + 3600*dt)
            self.selectHours()

        elif currentPosition <= len(f"{h}:{m}"):
            self.setValue(currentValue + 60*dt)
            self.selectMinutes()

        else:
            self.setValue(currentValue + dt)
            self.selectSeconds()

    def keyPressEvent(self, event):
        selectedText = self.lineEdit().selectedText()

        if ":" in selectedText:
            if event.key() not in (Qt.Key_Right, Qt.Key_Left):
                return

        selectionStart = self.lineEdit().selectionStart()
        selectionEnd = selectionStart + len(selectedText)
        currentPosition = self.lineEdit().cursorPosition()
        text = self.text()
        textBeforeCursor = text[:currentPosition]
        textAfterCursor = text[currentPosition:]

        matches = regex.findall(r"^(\d+):(\d+):(\d+(?:\.\d*))$", text)

        if matches:
            (h, m, s), = matches

        else:
            h = m = s = ""

        if event.key() == Qt.Key_Right and event.modifiers() == Qt.ControlModifier:
            if currentPosition <= len(h):
                self.selectMinutes()

            elif currentPosition <= len(f"{h}:{m}"):
                self.selectSeconds()

            return

        if event.key() == Qt.Key_Left and event.modifiers() == Qt.ControlModifier:
            if currentPosition >= len(f"{h}:{m}:"):
                self.selectMinutes()

            elif currentPosition >= len(f"{h}:"):
                self.selectHours()

            return

        if event.key() == Qt.Key_Backspace:
            if selectedText == "" and textBeforeCursor.endswith(":"):
                return

        if event.key() == Qt.Key_Delete:
            if selectedText == "" and textAfterCursor.startswith(":"):
                return

        if event.key() == Qt.Key_Colon:
            if textAfterCursor.startswith(":") and not selectedText:
                nextColon = textAfterCursor.find(":", 1)

                if nextColon >= 0:
                    self.lineEdit().setSelection(len(textBeforeCursor) + 1, nextColon - 1)

                else:
                    self.lineEdit().setSelection(len(textBeforeCursor) + 1, len(textAfterCursor) - 1)

            return

        ret = super().keyPressEvent(event)

        maxhours = int(self.maximum()//3600)
        maxhourdigits = 1

        while maxhours > 10:
            maxhourdigits += 1
            maxhours //= 10

        if Qt.Key_0 <= event.key() <= Qt.Key_9:
            if currentPosition == len(h) == maxhourdigits - 1:
                self.selectMinutes()

            elif len(selectedText) == 1 and selectionEnd == maxhourdigits:
                self.selectMinutes()

            elif currentPosition == len(f"{h}:{m}") and len(m) == 1:
                self.selectSeconds()

            elif len(selectedText) == 1 and selectionEnd == len(f"{h}:00"):
                self.selectSeconds()

    def selectHours(self):
        text = self.text()
        matches = regex.findall(r"^(\d+):(\d+):(\d+(?:\.\d*))$", text)

        if matches:
            (h, m, s), = matches
            self.lineEdit().setSelection(0, len(h))

    def selectMinutes(self):
        text = self.text()
        matches = regex.findall(r"^(\d+):(\d+):(\d+(?:\.\d*))$", text)

        if matches:
            (h, m, s), = matches
            self.lineEdit().setSelection(len(f"{h}:"), len(m))

    def selectSeconds(self):
        text = self.text()
        matches = regex.findall(r"^(\d+):(\d+):(\d+(?:\.\d*))$", text)

        if matches:
            (h, m, s), = matches
            self.lineEdit().setSelection(len(f"{h}:{m}:"), len(s))
