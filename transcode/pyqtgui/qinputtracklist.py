from PyQt5.QtCore import (Qt, pyqtSignal, QFileInfo)
from PyQt5.QtWidgets import (QLabel, QMessageBox, QPushButton,
                             QTreeView, QProgressDialog, QFileIconProvider)
from PyQt5.QtGui import (QFont, QIcon, QBrush)

from .qitemmodel import QItemModel, Node, ChildNodes
from transcode.containers.basereader import BaseReader, Track
import sys
import traceback
import threading
import av
import os
import types
import transcode

from .qlangselect import LANGUAGES
icons = QFileIconProvider()


class BaseInputCol(object):
    fontmain = QFont("DejaVu Serif", 8)
    fontalt = QFont("DejaVu Serif", 12, QFont.Bold, italic=True)

    flags = Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsDragEnabled
    textalign = Qt.AlignLeft | Qt.AlignVCenter
    bgdata = QBrush()
    itemDelegate = None

    def __init__(self, input_files, attrname=None):
        self.input_files = input_files
        self.attrname = attrname

    def editdata(self, index, obj):
        return getattr(obj, self.attrname)

    def seteditdata(self, index, obj, data):
        setattr(obj, attrname, data)

    def font(self, index, obj):
        if isinstance(obj, BaseReader):
            return self.fontalt

        return self.fontmain


class FileTrackCol(BaseInputCol):
    headerdisplay = "File/Track"
    width = 240
    flags = Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsDragEnabled

    def __init__(self, input_files):
        super().__init__(input_files, "name")

    def display(self, index, obj):
        if isinstance(obj, BaseReader):
            return f"{obj.config.input_files.index(obj)}: {obj.inputpathrel}"

        elif isinstance(obj, Track):
            if hasattr(obj, "name") and obj.name:
                return f"{obj.container.tracks.index(obj)}: {obj.name}"

            elif obj.type == "video":
                return f"{obj.container.tracks.index(obj)}: Video"

            elif obj.type == "audio":
                return f"{obj.container.tracks.index(obj)}: Audio"

            elif obj.type == "subtitle":
                return f"{obj.container.tracks.index(obj)}: Subtitle"

            return f"{obj.container.tracks.index(obj)}: {obj}"

    def tooltip(self, index, obj):
        if isinstance(obj, BaseReader):
            mod = obj.__class__.__module__

            if mod.split(".")[:2] == ["transcode", "containers"]:
                mod = ".".join(mod.split(".")[2:])

            return f"{obj.config.input_files.index(obj)}: {obj.inputpathabs}"

        elif isinstance(obj, Track):
            if hasattr(obj, "name") and obj.name:
                return f"{obj.container.tracks.index(obj)}: {obj.name}"

            elif obj.type == "video":
                return f"{obj.container.tracks.index(obj)}: Video"

            elif obj.type == "audio":
                return f"{obj.container.tracks.index(obj)}: Audio"

            elif obj.type == "subtitle":
                return f"{obj.container.tracks.index(obj)}: Subtitle"

            return f"{obj.container.tracks.index(obj)}: {obj}"

    def icon(self, index, obj):
        if isinstance(obj, Track):
            if obj.type == "video":
                return QIcon.fromTheme("video-x-generic")

            if obj.type == "audio":
                return QIcon.fromTheme("audio-x-generic")

            if obj.type == "subtitle":
                return QIcon.fromTheme("text-x-generic")

        elif isinstance(obj, BaseReader):
            return icons.icon(QFileInfo(obj.inputpathrel))


class LanguageCol(BaseInputCol):
    width = 96
    headerdisplay = "Language"
    flags = Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsDragEnabled

    def __init__(self, input_files):
        super().__init__(input_files, "language")

    def display(self, index, obj):
        if isinstance(obj, Track):
            try:
                lang = obj.language

            except AttributeError:
                lang = None

            if lang is None:
                return "Unknown (und)"

            return f"{LANGUAGES.get(lang, 'Unknown')} ({lang})"

    tooltip = display

    def itemDelegate(self, parent):
        return LanguageDelegate(parent)


class InputTypeCol(BaseInputCol):
    width = 128
    headerdisplay = "Format/Codec"

    def display(self, index, obj):
        if isinstance(obj, BaseReader):
            return obj.fmtname

        elif isinstance(obj, Track):
            codec = obj.codec

            try:
                codec_long = av.Codec(codec, "r").long_name

            except:
                codec_long = "Unknown"

            return f"{codec_long} ({codec})"

    def tooltip(self, index, obj):
        if isinstance(obj, BaseReader):
            mod = obj.__class__.__module__

            if mod.split(".")[:2] == ["transcode", "containers"]:
                mod = ".".join(mod.split(".")[2:])

            return f"{obj.fmtname}\n"\
                f"[{mod}.{obj.__class__.__name__}]"

        elif isinstance(obj, Track):
            codec = obj.codec

            try:
                codec_long = av.Codec(codec, "r").long_name

            except:
                codec_long = "Unknown"

            return f"{codec_long} ({codec})"


class InputFmtCol(BaseInputCol):
    width = 192
    headerdisplay = "Track Format"

    def display(self, index, obj):
        if isinstance(obj, BaseReader):
            return None

        elif isinstance(obj, Track):
            fmtlist = []

            if obj.type == "video":
                if obj.width and obj.height:
                    fmtlist.append(f"{obj.width}×{obj.height}")

                if obj.sar:
                    fmtlist.append(f"SAR: {obj.sar}")

                if obj.width and obj.height and obj.sar:
                    fmtlist.append(f"DAR: {obj.sar*obj.width/obj.height}")

                if obj.rate:
                    fmtlist.append(f"{obj.rate} fps")

                if obj.format:
                    fmtlist.append(f"{obj.format}")

            elif obj.type == "audio":
                if obj.rate:
                    fmtlist.append(f"{obj.rate}Hz")

                if obj.layout:
                    fmtlist.append(f"{obj.layout}")

                if obj.format:
                    fmtlist.append(f"{obj.format}")

            return ", ".join(fmtlist)

    tooltip = display


class MediaLoad(QProgressDialog):
    progressstarted = pyqtSignal(float)
    progress = pyqtSignal(float)
    progresscomplete = pyqtSignal(float)
    exceptionCaptured = pyqtSignal(type, BaseException, types.TracebackType)

    def __init__(self, fileName, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setAutoClose(True)
        self.setAutoReset(False)
        self.setWindowTitle("Scanning...")
        self.setLabel(QLabel(f"Scanning {fileName}..."))

        self.cancelButton = QPushButton("&Cancel")
        self.setCancelButton(self.cancelButton)
        self.cancelButton.clicked.connect(self.cancel)
        self.stopped = False

        self.fileName = fileName

        self.progressstarted.connect(self.setMaximum)
        self.progress.connect(self.updateValue)
        self.progresscomplete.connect(self.done)
        self.progresscomplete.connect(self.close)
        self.exceptionCaptured.connect(self.handleException)

        self.input_file = None
        self.thread = None

    def load(self):
        try:
            self.input_file = transcode.open(self.fileName)

            if hasattr(self.input_file, "scan") and callable(self.input_file.scan):
                self.input_file.scan(self.progressStarted,
                                     self.packetRead, self.progressComplete)

            self.progressComplete()

        except SystemExit:
            return

        except BaseException as exc:
            self.exceptionCaptured.emit(*sys.exc_info())

    def exec_(self):
        self.thread = threading.Thread(target=self.load)
        self.thread.start()
        return super().exec_()

    def progressStarted(self, duration):
        if self.stopped:
            sys.exit()

        self.progressstarted.emit(duration)

    def packetRead(self, pts_time):
        if self.stopped:
            sys.exit()

        self.progress.emit(pts_time)

    def updateValue(self, value):
        if value > self.value():
            self.setValue(value)

    def progressComplete(self):
        self.progresscomplete.emit(1)

    def cancel(self):
        self.stopped = True

        if self.thread is not None:
            self.thread.join()

        self.setValue(0)
        super().cancel()

    def handleException(self, cls, exc, tb):
        excmsg = QMessageBox(self)
        excmsg.setWindowTitle("Error")
        excmsg.setText("An exception was encountered\n\n%s" %
                       "".join(traceback.format_exception(cls, exc, tb)))
        excmsg.setStandardButtons(QMessageBox.Ok)
        excmsg.setIcon(QMessageBox.Critical)
        excmsg.exec_()
        self.close()


class InputFileModel(QItemModel):
    def dropItems(self, items, action, row, column, parent):
        node = self.getNode(parent)

        if row == -1:
            row = self.rowCount(parent)

        j = 0

        if action == Qt.MoveAction:
            for k, item in enumerate(items):
                old_row = node.children.index(item)
                self.moveRow(old_row, row + k - j, parent, parent)

                if old_row < row:
                    j += 1

        return True

    def canDropUrls(self, urls, action, row, column, parent):
        if parent.isValid():
            return False

        for url in urls:
            if url.scheme() != "file":
                return False

            if not os.path.isfile(url.path()):
                return False

        return True

    def dropUrls(self, urls, action, row, column, parent):
        if row == -1:
            row = self.rowCount(parent)

        k = 0
        newfiles = []

        for url in urls:
            progress = MediaLoad(url.path())

            if progress.exec_():
                newfiles.append(progress.input_file)

            else:
                return False

        self.insertRows(row, newfiles, parent)
        return True

    def canDropItems(self, items, action, row, column, parent):
        if parent.isValid():
            return False

        for item in items:
            if item not in self.root.children:
                return False

        return True

    def supportedDropActions(self):
        return Qt.MoveAction | Qt.CopyAction

    def supportedDragActions(self):
        return Qt.MoveAction | Qt.CopyAction


class InputFilesNode(Node):
    def _wrapChildren(self, children):
        return InputFilesNodes.fromValues(children, self)


class InputFilesNodes(ChildNodes):
    @staticmethod
    def _wrap(value):
        return InputFileNode(value)


class InputFileNode(Node):
    def _iterChildren(self):
        return iter(self.value.tracks)


class QInputTrackList(QTreeView):
    contentsModified = pyqtSignal()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setMinimumWidth(640)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setInputFiles(None)
        self.setDefaultDropAction(Qt.CopyAction)

    def setInputFiles(self, input_files):
        self.input_files = input_files

        if input_files is not None:
            cols = [
                FileTrackCol(input_files),
                InputTypeCol(input_files),
                InputFmtCol(input_files),
                LanguageCol(input_files),
            ]

            root = InputFilesNode(input_files)
            model = InputFileModel(root, cols)
            self.setModel(model)
            model.dataChanged.connect(self.contentsModified)

            for k, col in enumerate(cols):
                if hasattr(col, "width"):
                    self.setColumnWidth(k, col.width)

        else:
            self.setModel(QItemModel(Node(None), []))
