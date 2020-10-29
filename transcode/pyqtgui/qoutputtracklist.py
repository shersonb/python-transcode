from PyQt5.QtCore import (Qt, pyqtSignal, pyqtBoundSignal)
from PyQt5.QtWidgets import (QHBoxLayout, QAbstractItemView, QMessageBox, QPushButton,
                             QTreeView, QComboBox, QDoubleSpinBox, QItemDelegate,
                             QComboBox, QWidget)
from PyQt5.QtGui import QFont, QIcon, QBrush

from .qitemmodel import QItemModel, Node, ChildNodes

from .qlangselect import LanguageDelegate, LANGUAGES
from transcode.containers.basereader import Track as InputTrack
from transcode.containers.basewriter import Track as OutputTrack
from transcode.encoders import vencoders, aencoders, sencoders
from transcode.encoders import createConfigObj as createCodecConfigObj
from transcode.filters.filterchain import FilterChain
from transcode.filters.base import BaseFilter
import av
from functools import partial


class BaseOutputTrackCol(object):
    font = QFont("DejaVu Serif", 8)
    flags = Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsDragEnabled
    textalign = Qt.AlignLeft | Qt.AlignVCenter
    bgdata = QBrush()
    itemDelegate = None

    def __init__(self, input_files, filters, output_file, attrname=None):
        self.input_files = input_files
        self.filters = filters
        self.output_file = output_file
        self.attrname = attrname

    def editdata(self, index, track):
        return getattr(track, self.attrname)

    def seteditdata(self, index, track, data):
        oldattr = getattr(track, self.attrname) or ""

        if oldattr != data:
            setattr(track, self.attrname, data)
            return True

        return False


class QCodecSelection(QWidget):
    def __init__(self, track, savedencoders, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.track = track
        self.savedencoders = savedencoders

        layout = QHBoxLayout()
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

        self.encoderSelectionComboBox = QComboBox(self)
        layout.addWidget(self.encoderSelectionComboBox)

        self.configBtn = QPushButton(self)
        layout.addWidget(self.configBtn)

        self.configBtn.setIcon(QIcon.fromTheme("preferences-other"))

        self.encoderSelectionComboBox.addItem("Copy Track", None)
        self.encoderSelectionComboBox.insertSeparator(
            self.encoderSelectionComboBox.count())

        if track.type == "video":
            common_encoders = ["libx265", "libx264", "mpeg2video"]
            encoders = vencoders

        elif track.type == "audio":
            common_encoders = ["dca", "ac3",
                               "libfdk_aac", "aac", "mp3", "flac"]
            encoders = aencoders

        elif track.type == "subtitle":
            common_encoders = ["ass", "srt"]
            encoders = sencoders

        for key in common_encoders:
            try:
                self.encoderSelectionComboBox.addItem(
                    f"{encoders[key]} ({key})", key)

            except KeyError:
                pass

        self.encoderSelectionComboBox.insertSeparator(
            self.encoderSelectionComboBox.count())

        for key, encoder in sorted(encoders.items(), key=lambda item: item[1]):
            if key in common_encoders:
                continue
            self.encoderSelectionComboBox.addItem(f"{encoder} ({key})", key)

        self.encoderSelectionComboBox.currentIndexChanged.connect(
            self.encoderSelectionComboBoxChanged)
        self.configBtn.clicked.connect(self.configureCodec)
        self.configBtn.setEnabled(track.encoder is not None)

    def encoderSelectionComboBoxChanged(self, value):
        data = self.encoderSelectionComboBox.currentData()

        if (id(self.track), data) not in self.savedencoders and data is not None:
            self.savedencoders[id(self.track),
                               data] = createCodecConfigObj(data)

        self.configBtn.setDisabled(data is None)

    def configureCodec(self):
        data = self.encoderSelectionComboBox.currentData()
        encoder = self.savedencoders[id(self.track), data]

        dlg = encoder.copy().QtDlg(self)

        if dlg is not None and dlg.exec_():
            encoder.__setstate__(dlg.encoder.__getstate__())

    def setEncoderSelection(self, encoder):
        self.configBtn.setEnabled(encoder is not None)

        if encoder is not None:
            self.savedencoders[id(self.track), encoder.codec] = encoder

        if encoder:
            codecindex = self.encoderSelectionComboBox.findData(encoder.codec)

        else:
            codecindex = self.encoderSelectionComboBox.findData(None)

        self.encoderSelectionComboBox.blockSignals(True)

        if codecindex >= 0:
            self.encoderSelectionComboBox.setCurrentIndex(codecindex)

        else:
            self.encoderSelectionComboBox.setCurrentIndex(0)

        self.encoderSelectionComboBox.blockSignals(False)

    def encoderSelection(self):
        data = self.encoderSelectionComboBox.currentData()
        return self.savedencoders.get((id(self.track), data))


class CodecDelegate(QItemDelegate):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.savedencoders = {}

    def createEditor(self, parent, option, index):
        track = index.data(Qt.UserRole)
        editor = QCodecSelection(track, self.savedencoders, parent)
        editor.encoderSelectionComboBox.currentIndexChanged.connect(partial(self.setModelData, editor=editor,
                                                                            model=index.model(), index=index))
        return editor

    def setEditorData(self, editor, index):
        encoder = index.data(Qt.EditRole)
        editor.setEncoderSelection(encoder)

    def setModelData(self, editor, model, index):
        track = index.data(Qt.UserRole)
        encoder = editor.encoderSelection()
        model.setData(index, encoder, Qt.EditRole)

    def updateEditorGeometry(self, editor, option, index):
        editor.setGeometry(option.rect)


class FilterEditor(QPushButton):
    contentsModified = pyqtSignal()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._filters = None
        self.setIcon(QIcon.fromTheme("preferences-other"))
        self.clicked.connect(self.configureFilters)

    def filters(self):
        return self._filters

    def setFilters(self, filters):
        self._filters = filters

    def configureFilters(self):
        if self.filters() is not None:
            dlg = self.filters().QtDlg()
            dlg.settingsApplied.connect(self.contentsModified)
            dlg.exec_()


class FiltersDelegate(QItemDelegate):
    contentsModified = pyqtSignal()

    def createEditor(self, parent, option, index):
        editor = FilterEditor(parent)
        editor.contentsModified.connect(self.contentsModified)
        return editor

    def setEditorData(self, editor, index):
        filters = index.data(Qt.EditRole)

        if filters is None:
            track = index.data(Qt.UserRole)
            track.filters = filters = FilterChain([])

        editor.setFilters(filters)

    def setModelData(self, editor, model, index):
        track = index.data(Qt.UserRole)
        filters = editor.filters()
        model.setData(index, filters, Qt.EditRole)

    def updateEditorGeometry(self, editor, option, index):
        editor.setGeometry(option.rect)


class TitleCol(BaseOutputTrackCol):
    headerdisplay = "Track"
    width = 256
    flags = Qt.ItemIsSelectable | Qt.ItemIsEditable | Qt.ItemIsEnabled | Qt.ItemIsDragEnabled

    def __init__(self, input_files, filters, output_file):
        super().__init__(input_files, filters, output_file, "name")

    def display(self, index, track):
        name = self.editdata(index, track)

        if name:
            return f"{self.output_file.tracks.index(track)}: {name}"

        elif track.type == "video":
            return f"{self.output_file.tracks.index(track)}: Video"

        elif track.type == "audio":
            return f"{self.output_file.tracks.index(track)}: Audio"

        elif track.type == "subtitle":
            return f"{self.output_file.tracks.index(track)}: Subtitle"

        return f"{self.output_file.tracks.index(track)}: {track}"

    tooltip = display

    def icon(self, index, track):
        if track.type == "video":
            return QIcon.fromTheme("video-x-generic")

        if track.type == "audio":
            return QIcon.fromTheme("audio-x-generic")

        if track.type == "subtitle":
            return QIcon.fromTheme("text-x-generic")


class MapCol(BaseOutputTrackCol):
    width = 72
    headerdisplay = "Source"

    def display(self, index, track):
        if isinstance(track.source, InputTrack):
            file_index = self.input_files.index(track.source.container)
            return f"{file_index}:{track.source.track_index}"

        elif track.source in self.filters:
            filter_index = self.filters.index(track.source)
            return f"filters:{filter_index}"

        return ""

    tooltip = display


class OutputLangCol(BaseOutputTrackCol):
    width = 120
    headerdisplay = "Language"
    flags = Qt.ItemIsSelectable | Qt.ItemIsEditable | Qt.ItemIsEnabled | Qt.ItemIsDragEnabled

    def __init__(self, input_files, filters, output_file):
        super().__init__(input_files, filters, output_file, "language")

    def display(self, index, track):
        lang = self.editdata(index, track)

        if lang is None:
            return "Unknown (und)"

        return f"{LANGUAGES.get(lang, 'Unknown')} ({lang})"

    tooltip = display

    def itemDelegate(self, parent):
        return LanguageDelegate(parent)


class OutputCodecCol(BaseOutputTrackCol):
    headerdisplay = "Codec"
    flags = Qt.ItemIsSelectable | Qt.ItemIsEditable | Qt.ItemIsEnabled | Qt.ItemIsDragEnabled
    width = 256

    def __init__(self, input_files, filters, output_file):
        super().__init__(input_files, filters, output_file, "encoder")

    def display(self, index, track):
        encoder = self.editdata(index, track)

        if encoder:
            try:
                c = av.codec.Codec(encoder.codec, "w")
                return f"{c.long_name} ({encoder.codec})"

            except:
                return f"Unknown ({encoder.codec})"

        else:
            try:
                c = av.codec.Codec(track.source.codec, "w")
                return f"{c.long_name} ({track.source.codec}, copy)"

            except:
                return f"Unknown ({track.source.codec}, copy)"

    tooltip = display

    def itemDelegate(self, parent):
        return CodecDelegate(parent)


class FiltersCol(BaseOutputTrackCol):
    headerdisplay = "Filters"

    def __init__(self, input_files, filters, output_file):
        super().__init__(input_files, filters, output_file, "filters")

    def display(self, index, track):
        filters = self.editdata(index, track)

        if filters is None or len(filters) == 0:
            return "No filters"

        elif len(filters) == 1:
            return "1 Filter"

        return f"{len(filters)} Filters"

    tooltip = display

    def itemDelegate(self, parent):
        return FiltersDelegate(parent)

    def flags(self, index, track):
        if track.encoder is not None:
            return Qt.ItemIsSelectable | Qt.ItemIsEditable | Qt.ItemIsEnabled | Qt.ItemIsDragEnabled

        return Qt.ItemIsSelectable | Qt.ItemIsDragEnabled


class DelayDelegate(QItemDelegate):
    def createEditor(self, parent, option, index):
        editor = QDoubleSpinBox(parent)
        editor.setMinimum(0)
        editor.setDecimals(3)
        editor.setSingleStep(0.125)
        editor.setSpecialValueText("No delay")
        editor.setSuffix(" seconds")
        editor.setMaximum(3*3600)
        return editor

    def setEditorData(self, editor, index):
        editor.setValue(index.data(Qt.EditRole))

    def setModelData(self, editor, model, index):
        model.setData(index, editor.value(), Qt.EditRole)

    def updateEditorGeometry(self, editor, option, index):
        editor.setGeometry(option.rect)


class DelayCol(BaseOutputTrackCol):
    headerdisplay = "Delay"
    width = 128
    flags = Qt.ItemIsSelectable | Qt.ItemIsEditable | Qt.ItemIsEnabled | Qt.ItemIsDragEnabled

    def __init__(self, input_files, filters, output_file):
        super().__init__(input_files, filters, output_file, "delay")

    def display(self, index, track):
        delay = self.editdata(index, track)

        if isinstance(delay, (int, float)):
            return f"{delay:.3f} seconds"

        return "0.000 seconds"

    tooltip = display

    def itemDelegate(self, parent):
        return DelayDelegate(parent)


class OutputFmtCol(BaseOutputTrackCol):
    width = 192
    headerdisplay = "Format"

    def display(self, index, obj):
        if isinstance(obj, OutputTrack):
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


class OutputTrackModel(QItemModel):
    def dropItems(self, items, action, row, column, parent):
        if parent.isValid():
            return False

        if row == -1:
            row = self.rowCount(parent)

        j = 0

        if action == Qt.CopyAction:
            for k, item in enumerate(items):
                newtrack = self.root.value.trackclass(item.value,
                                                      name=item.value.name, language=item.value.language)

                self.insertRow(row + k - j, newtrack, parent)

        elif action == Qt.MoveAction:
            for k, item in enumerate(items):
                old_row = self.root.index(item)
                self.moveRow(old_row, row + k - j, parent, parent)

                if old_row < row:
                    j += 1

        return True

    def canDropItems(self, items, action, row, column, parent):
        if parent.isValid():
            return False

        parent_obj = parent.data(Qt.UserRole)

        if action == Qt.CopyAction:
            for item in items:
                if not isinstance(item.value, (InputTrack, BaseFilter)):
                    return False

        elif action == Qt.MoveAction:
            for item in items:
                if not isinstance(item.value, OutputTrack) or item not in self.root.children:
                    return False

        return True

    def supportedDropActions(self):
        return Qt.MoveAction | Qt.CopyAction


class OutputFileNode(Node):
    def _iterChildren(self):
        return iter(self.value.tracks)

    def _wrapChildren(self, children):
        return OutputTrackNodes.fromValues(children, self)


class OutputTrackNodes(ChildNodes):
    def _append(self, value):
        self.parent.value.tracks.append(value)

    def _insert(self, index, value):
        self.parent.value.tracks.insert(index, value)

    def _extend(self, values):
        self.parent.value.tracks.extend(values)

    def _delitem(self, index):
        del self.parent.value.tracks[index]

    def _setitem(self, index, value):
        self.parent.value.tracks[index] = value


class OutputTrackList(QTreeView):
    contentsModified = pyqtSignal()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFont(QFont("DejaVu Serif", 8))
        self.setMinimumWidth(640)

        self.setEditTriggers(QTreeView.SelectedClicked |
                             QTreeView.EditKeyPressed)

        self.setDragDropMode(QTreeView.DragDrop)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDragDropOverwriteMode(False)
        self.setDropIndicatorShown(True)
        self.viewport().setAcceptDrops(True)

        self.setIndentation(0)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setOutputFile(None)

    def setOutputFile(self, output_file=None):
        self.output_file = output_file

        if output_file is not None:
            input_files = output_file.config.input_files
            filters = output_file.config.filter_chains

            cols = [
                TitleCol(input_files, filters, output_file),
                MapCol(input_files, filters, output_file),
                OutputFmtCol(input_files, filters, output_file),
                OutputLangCol(input_files, filters, output_file),
                OutputCodecCol(input_files, filters, output_file),
                FiltersCol(input_files, filters, output_file),
                DelayCol(input_files, filters, output_file)
            ]

            if hasattr(output_file, "trackCols") and callable(output_file.trackCols):
                for col in output_file.trackCols():
                    cols.append(col(input_files, filters, output_file))

            root = OutputFileNode(output_file)
            self.setModel(OutputTrackModel(root, cols))
            self.model().dataChanged.connect(self.contentsModified)

            for k, col in enumerate(cols):
                if hasattr(col, "width"):
                    self.setColumnWidth(k, col.width)

                if callable(col.itemDelegate):
                    delegate = col.itemDelegate(self)

                    if hasattr(delegate, "contentsModified") and \
                            isinstance(delegate.contentsModified, pyqtBoundSignal):
                        delegate.contentsModified.connect(
                            self.contentsModified)

                    self.setItemDelegateForColumn(k, delegate)

        else:
            self.setModel(QItemModel(Node(None), []))

    def currentChanged(self, newindex, oldindex):
        if oldindex.isValid():
            for j in range(self.model().columnCount()):
                idx = self.model().index(oldindex.row(), j)

                if self.model().flags(idx) & Qt.ItemIsEditable:
                    self.closePersistentEditor(idx)

        if newindex.isValid():
            for j in range(self.model().columnCount()):
                idx = self.model().index(newindex.row(), j)

                if self.model().flags(idx) & Qt.ItemIsEditable:
                    self.openPersistentEditor(
                        self.model().index(newindex.row(), j))

    def keyPressEvent(self, event):
        key = event.key()
        modifiers = event.modifiers()
        idx = self.currentIndex()
        row = idx.row()
        col = idx.column()
        model = self.model()

        selected = sorted(idx.row()
                          for idx in self.selectionModel().selectedRows())

        if key == Qt.Key_Delete and modifiers == Qt.NoModifier and len(self.selectionModel().selectedRows()):
            self.askDeleteSelected()

        super().keyPressEvent(event)

    def askDeleteSelected(self):
        answer = QMessageBox.question(
            self, "Delete tracks", "Do you wish to delete the selected tracks? All encoder and settings associated with selected tracks will be lost!", QMessageBox.Yes | QMessageBox.No)

        if answer == QMessageBox.Yes:
            self.deleteSelected()

    def deleteSelected(self):
        selected = sorted(idx.row()
                          for idx in self.selectionModel().selectedRows())

        for k, row in enumerate(selected):
            self.model().removeRow(row - k)

        self.contentsModified.emit()
