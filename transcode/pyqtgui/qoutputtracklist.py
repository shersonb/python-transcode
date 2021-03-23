from PyQt5.QtCore import (Qt, pyqtSignal, pyqtBoundSignal)
from PyQt5.QtWidgets import (QHBoxLayout, QAbstractItemView, QMessageBox, QPushButton,
                             QTreeView, QComboBox, QDoubleSpinBox, QItemDelegate,
                             QComboBox, QWidget, QApplication, QMenu, QAction, QFileDialog)
from PyQt5.QtGui import QFont, QIcon, QBrush

from .qitemmodel import QItemModel, Node, ChildNodes, NoChildren

from .qlangselect import LanguageDelegate, LANGUAGES
from .treeview import TreeView as QTreeView
from transcode.containers.basereader import BaseReader
from transcode.containers.basereader import Track as InputTrack
from transcode.containers.basewriter import Track as OutputTrack
from transcode.encoders import vencoders, aencoders, sencoders
from transcode.encoders import createConfigObj as createCodecConfigObj
from transcode.filters.filterchain import FilterChain
from transcode.filters.base import BaseFilter
from transcode.config.ebml.filterchains import FilterChainElement, FilterElement
import av
from functools import partial
from itertools import count
from collections import OrderedDict
import sys


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

    def contextmenu(self, index, obj):
        return partial(self.createContextMenu, obj=obj, index=index)

    def createContextMenu(self, table, index, obj):
        menu = QMenu(table)
        selected = table.selectedIndexes()
        current = table.currentIndex()
        track = current.data(Qt.UserRole)

        configurefilter = QAction("Configure Filters...",
                        table, triggered=partial(table.configureFilters, track))

        importfilters = QAction("Load Filters...",
                        table, triggered=partial(table.importFilterChain, track))

        exportfilters = QAction("Save Filters...",
                        table, triggered=partial(table.exportFilterChain, track))

        if isinstance(track, OutputTrack):
            configureencoder = QAction("Configure Encoder...",
                         table, triggered=partial(table.configureEncoder, track.encoder))

        else:
            configureencoder = QAction("Configure Encoder...", table)


        configurefilter.setDisabled(track is None or track.encoder is None)
        importfilters.setDisabled(track is None or track.encoder is None)
        exportfilters.setDisabled(track is None or track.encoder is None)
        configureencoder.setDisabled(track is None or track.encoder is None)

        menu.addAction(configurefilter)
        menu.addAction(importfilters)
        menu.addAction(exportfilters)
        menu.addAction(configureencoder)

        delete = QAction("Delete selected...",
                         table, triggered=partial(table.askDeleteSelected))


        if len(selected) == 0 or any(not isinstance(index.data(Qt.UserRole), BaseReader) for index in selected):
            delete.setDisabled(True)

        menu.addAction(delete)
        return menu


class QCodecSelection(QWidget):
    contentsModified = pyqtSignal()

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

        else:
            common_encoders = ["libx265", "libx264", "mpeg2video",
                               "dca", "ac3",
                               "libfdk_aac", "aac", "mp3", "flac",
                               "ass", "srt"]

            
            encoders = OrderedDict()
            encoders.update(vencoders)
            encoders.update(aencoders)
            encoders.update(sencoders)

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
        if hasattr(dlg, "settingsApplied") and isinstance(dlg.settingsApplied, pyqtBoundSignal):
            dlg.settingsApplied.connect(self.contentsModified)

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
    contentsModified = pyqtSignal()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.savedencoders = {}

    def createEditor(self, parent, option, index):
        track = index.data(Qt.UserRole)
        editor = QCodecSelection(track, self.savedencoders, parent)
        editor.encoderSelectionComboBox.currentIndexChanged.connect(partial(self.setModelData, editor=editor,
                                                                            model=index.model(), index=index))
        editor.contentsModified.connect(self.contentsModified)
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
        if len(track.validate()):
            return QIcon.fromTheme("emblem-error")

        elif track.type == "video":
            return QIcon.fromTheme("video-x-generic")

        elif track.type == "audio":
            return QIcon.fromTheme("audio-x-generic")

        elif track.type == "subtitle":
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

        elif track.source is not None:
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
    def supportedDropActions(self):
        return Qt.MoveAction | Qt.CopyAction


class OutputFileNode(Node):
    def _iterChildren(self):
        return iter(self.value.tracks)

    def _wrapChildren(self, children):
        return OutputTrackNodes.fromValues(children, self)

    def canDropChildren(self, model, parent, items, row, action):
        if action == Qt.CopyAction:
            for item in items:
                if not isinstance(item.value, (InputTrack, BaseFilter, BaseReader)):
                    return False

        elif action == Qt.MoveAction:
            for item in items:
                if item not in self.children:
                    return False

        return True

    def dropChildren(self, model, parent, items, row, action):
        if action == Qt.CopyAction:
            #K = count(row)
            newtracks = []

            for item in items:
                if isinstance(item.value, BaseReader):
                    for track in item.value.tracks:
                        newtrack = self.value.createTrack(track,
                                                         name=track.name, language=track.language)

                        #model.insertRow(next(K), newtrack, parent)
                        newtracks.append(newtrack)

                elif isinstance(item.value, BaseFilter):
                    newtrack = self.value.createTrack(item.value)
                    #model.insertRow(next(K), newtrack, parent)
                    newtracks.append(newtrack)

                else:
                    newtrack = self.value.createTrack(item.value,
                                                     name=item.value.name, language=item.value.language)

                    #model.insertRow(next(K), newtrack, parent)
                    newtracks.append(newtrack)

            model.insertRows(row, newtracks, parent)

        elif action == Qt.MoveAction:
            j = 0

            for k, item in enumerate(items, row):
                old_row = self.children.index(item)
                model.moveRow(old_row, k - j, parent)

                if old_row < row:
                    j += 1

        return True

    def canDropItems(self, model, parent, items, action):
        return self.canDropChildren(model, parent, items, len(self.children), action)

    def dropItems(self, model, parent, items, action):
        return self.dropChildren(model, parent, items, len(self.children), action)


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

        #self.setEditTriggers(QTreeView.SelectedClicked |
                             #QTreeView.EditKeyPressed)

        self.setDragDropMode(QTreeView.DragDrop)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setDragEnabled(True)
        self.setDragDropOverwriteMode(False)
        self.setDropIndicatorShown(True)
        # self.viewport().setAcceptDrops(True)

        self.setIndentation(0)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QTreeView.ExtendedSelection)
        self.setOutputFile(None)

    def dragMoveEvent(self, event):
        ret = super().dragMoveEvent(event)

        if event.source() is not self:
            event.setDropAction(Qt.CopyAction)

        return ret

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

            self.setAcceptDrops(True)
            self.viewport().setAcceptDrops(True)

        else:
            self.setModel(QItemModel(Node(None), []))
            self.setAcceptDrops(False)

    def currentChanged(self, newindex, oldindex):
        if oldindex.isValid():
            for j in range(self.model().columnCount(oldindex.parent())):
                idx = oldindex.sibling(oldindex.row(), j)

                if self.model().flags(idx) & Qt.ItemIsEditable:
                    self.closePersistentEditor(idx)

        if newindex.isValid():
            for j in range(self.model().columnCount(newindex.parent())):
                idx = oldindex.sibling(newindex.row(), j)

                if (self.model().flags(idx) & Qt.ItemIsEditable):
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

    def configureEncoder(self, encoder):
        dlg = encoder.QtDlg(self)
        dlg.settingsApplied.connect(self.contentsModified)
        dlg.exec_()

    def configureFilters(self, track):
        if track.filters is None:
            track.filters = FilterChain([])

        dlg = track.filters.QtDlg(self)
        dlg.settingsApplied.connect(self.contentsModified)
        dlg.exec_()

    def exportFilterChain(self, track):
        filefilters = "Filterchains (*.filterchain *.filterchain.gz *.filterchain.bz2 *.filterchain.xz)"

        defaultname = "untitled.filterchain.xz"
        fileName, _ = QFileDialog.getSaveFileName(self, "Save File",
                                                  defaultname, filefilters)

        if fileName:
            try:
                FilterChainElement.save(track.filters, fileName)

            except:
                self._handleException(*sys.exc_info())

    def importFilterChain(self, track):
        filefilters = "Filterchains (*.filterchain *.filterchain.gz *.filterchain.bz2 *.filterchain.xz)"

        defaultname = "untitled.filterchain.xz"
        fileName, _ = QFileDialog.getOpenFileName(self, "Save File",
                                                  defaultname, filefilters)

        if fileName:
            try:
                filters = FilterChainElement.load(fileName)

            except:
                self._handleException(*sys.exc_info())

            if not track.filters or QMessageBox.question(
            self, "Replace Filters", "Do you wish to replace the current filters for the selected track? Current filters associated with selected track will be lost!", QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
                track.filters = filters
                self.contentsModified.emit()
