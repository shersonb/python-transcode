from PyQt5.QtWidgets import QApplication, QWidget
import sys
from PyQt5.QtCore import (Qt, QAbstractListModel, QAbstractItemModel, QAbstractTableModel, QModelIndex,
                          QVariant, QItemSelectionModel, QItemSelection, pyqtSignal, pyqtSlot, QMimeData, QByteArray,
                          QDataStream, QIODevice, QSortFilterProxyModel)
from PyQt5.QtWidgets import (QDialog, QLabel, QListWidgetItem, QListView, QVBoxLayout, QHBoxLayout,
                             QAbstractItemView, QMessageBox, QPushButton, QTreeView, QTableView, QHeaderView,
                             QLineEdit, QComboBox, QFileDialog, QCheckBox, QDoubleSpinBox, QItemDelegate, QComboBox,
                             QCompleter)
from PyQt5.QtGui import QFont, QIcon, QDrag, QBrush, QPainter, QStandardItemModel, QStandardItem, QPen, QCursor

from .qobjectitemmodel import QObjectItemModel
from .qinputtracklist import InputTreeView
from .qvfilteredit import VFilterEditDlg
from transcode.containers.basereader import BaseReader
from transcode.containers.basereader import Track as InputTrack
from transcode.encoders import vencoders, aencoders, sencoders
from transcode.encoders import createConfigObj as createCodecConfigObj
from transcode.filters.filterchain import FilterChain
from transcode.objwrapper import Collection, ObjectWrapper
import sys
import traceback
import json
import regex
import av
import os
from functools import partial
import faulthandler
faulthandler.enable()

d = json.JSONDecoder()
f = open("/usr/share/iso-codes/json/iso_639-3.json", "r")
iso639_3 = d.decode(f.read())["639-3"]
LANGUAGES = {lang["alpha_3"]: lang["name"] for lang in iso639_3}
f.close()
del f

class BaseOutputTrackCol(object):
    font = QFont("DejaVu Serif", 8)
    flags = Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsDragEnabled | Qt.ItemIsDropEnabled
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
        setattr(track, self.attrname, data)

class LanguageDelegate(QItemDelegate):
    def createEditor(self, parent, option, index):
        editor = QComboBox(parent)

        editor.addItem("Unknown (und)", None)
        editor.insertSeparator(editor.count())

        common_langs = ["eng", "deu", "ita", "spa", "fra", "por", "nld", "swe", "nor", "fin", "pol", "ron", "rus", "tur", "vie", "kor", "arz", "pes", "hin", "zho", "jpn"]

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
        self.encoderSelectionComboBox.insertSeparator(self.encoderSelectionComboBox.count())

        if track.type == "video":
            common_encoders = ["libx265", "libx264", "mpeg2video"]
            encoders = vencoders

        elif track.type == "audio":
            common_encoders = ["dca", "ac3", "libfdk_aac", "aac", "mp3", "flac"]
            encoders = aencoders

        elif track.type == "subtitle":
            common_encoders = ["ass", "srt"]
            encoders = sencoders

        for key in common_encoders:
            try:
                self.encoderSelectionComboBox.addItem(f"{encoders[key]} ({key})", key)

            except KeyError:
                pass

        self.encoderSelectionComboBox.insertSeparator(self.encoderSelectionComboBox.count())

        for key, encoder in sorted(encoders.items(), key=lambda item: item[1]):
            if key in common_encoders:
                continue
            self.encoderSelectionComboBox.addItem(f"{encoder} ({key})", key)

        self.encoderSelectionComboBox.currentIndexChanged.connect(self.encoderSelectionComboBoxChanged)
        self.configBtn.clicked.connect(self.configureCodec)

    def encoderSelectionComboBoxChanged(self, value):
        data = self.encoderSelectionComboBox.currentData()

        if (id(self.track), data) not in self.savedencoders and data is not None:
            self.savedencoders[id(self.track), data] = createCodecConfigObj(data)

        self.configBtn.setDisabled(data is None)

    def configureCodec(self):
        data = self.encoderSelectionComboBox.currentData()
        encoder = self.savedencoders[id(self.track), data]

        dlg = encoder.copy().QtDlg(self)

        if dlg is not None and dlg.exec_():
            encoder.__setstate__(dlg.encoder.__getstate__())

    def setEncoderSelection(self, encoder):
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
        if self.filters().type == "video":
            dlg = VFilterEditDlg(self.filters().copy(), self)

            if dlg.exec_():
                self.setFilters(dlg.filters)

class FiltersDelegate(QItemDelegate):
    def createEditor(self, parent, option, index):
        editor = FilterEditor(parent)
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
    flags = Qt.ItemIsSelectable | Qt.ItemIsEditable | Qt.ItemIsEnabled | Qt.ItemIsDragEnabled | Qt.ItemIsDropEnabled

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
        #input_files = self.config.getItems(self.input_files)

        if isinstance(track.source, InputTrack):
            file_index = self.input_files.index(track.source.container)
            return f"{file_index}:{track.source.track_index}"

        elif track.source in self.filters:
            filter_index = self.filters.index(track.source)
            return f"filters:{filter_index}"

        return "???"

    tooltip = display

class OutputLangCol(BaseOutputTrackCol):
    width = 120
    headerdisplay = "Language"
    flags = Qt.ItemIsSelectable | Qt.ItemIsEditable | Qt.ItemIsEnabled | Qt.ItemIsDragEnabled | Qt.ItemIsDropEnabled

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
    flags = Qt.ItemIsSelectable | Qt.ItemIsEditable | Qt.ItemIsEnabled | Qt.ItemIsDragEnabled | Qt.ItemIsDropEnabled
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
            return Qt.ItemIsSelectable | Qt.ItemIsEditable | Qt.ItemIsEnabled | Qt.ItemIsDragEnabled | Qt.ItemIsDropEnabled

        return Qt.ItemIsSelectable | Qt.ItemIsDragEnabled | Qt.ItemIsDropEnabled

class OutputListView(QTreeView):
    contentsChanged = pyqtSignal()

    def __init__(self, input_files, filters, output_file, *args, **kwargs):
        ### TODO: Include filters
        super().__init__(*args, **kwargs)
        self.input_files = input_files
        self.filters = filters
        self.output_file = output_file

        cols = [
                TitleCol(input_files, filters, output_file),
                MapCol(input_files, filters, output_file),
                OutputLangCol(input_files, filters, output_file),
                OutputCodecCol(input_files, filters, output_file),
                FiltersCol(input_files, filters, output_file)
            ]

        if hasattr(output_file, "trackCols") and callable(output_file.trackCols):
            for col in output_file.trackCols():
                cols.append(col(input_files, filters, output_file))

        self.setModel(QObjectItemModel(output_file.tracks, cols))

        for k, col in enumerate(cols):
            if callable(col.itemDelegate):
                self.setItemDelegateForColumn(k, col.itemDelegate(self))

        self.setItemsExpandable(False)
        self.setIndentation(0)
        self.setMinimumWidth(640)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.viewport().setAcceptDrops(True)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setDragDropMode(QTableView.DragDrop)
        self.setDragDropOverwriteMode(False)
        self.setDropIndicatorShown(True)
        self._dropIndex = None
        #self.currentIndexChanged.connect(self.currentRowChanged)

        for k, col in enumerate(cols):
            if hasattr(col, "width"):
                self.setColumnWidth(k, col.width)
        #for j in range(self.model().rowCount()):
            #for k in (2, 3):
                #index = self.model().index(j, k)
                #self.openPersistentEditor(index)

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
                    self.openPersistentEditor(self.model().index(newindex.row(), j))

    def dragLeaveEvent(self, event):
        self._dropIndex = None
        return super().dragLeaveEvent(event)

    #def startDrag(self, supportedActions):
        #drag = QDrag(self)
        #idx = self.currentIndex()
        #mimedata = self.model().mimeData([idx])

        ##if isinstance(item, movie.output.Track):
            ##mimedata.setText("output:%d" % self.mkvfile.tracks.index(item))

        #drag.setMimeData(mimedata)
        #drag.exec_(Qt.CopyAction | Qt.MoveAction, Qt.CopyAction)

    def dragMoveEvent(self, event):
        pos = event.pos()
        index = self.indexAt(pos)
        data = event.mimeData().text()

        if False and isinstance(event.source(), QInputTrackTree):
            event.setDropAction(Qt.CopyAction)

        elif event.source() is self:
            event.setDropAction(Qt.MoveAction)

        else:
            event.setDropAction(Qt.CopyAction)

        itemrect = self.visualRect(index)

        if index.row() < 0:
            self._dropIndex = self.model().rowCount()

        elif (event.pos().y() - itemrect.y()) < itemrect.height()/2:
            self._dropIndex = index.row()

        else:
            self._dropIndex = index.row() + 1


        #if event.source() == self:
            #if regex.match(r"^output:\d+$", data):
                #itemat = self.indexAt(pos)
                #itemrect = self.visualRect(itemat)
                #if itemat.row() < 0:
                    #dropindex = self.model().rowCount()
                #elif (event.pos().y() - itemrect.y()) < itemrect.height()/2:
                    #dropindex = itemat.row()
                #else:
                    #dropindex = itemat.row() + 1
                ##print(dropindex)
                #event.accept()
                #event.setDropAction(Qt.MoveAction)
                #return
            #event.accept()
        #elif isinstance(event.source(), InputTreeView):
            #event.setDropAction(Qt.CopyAction)
            #event.accept()
            #return
        #print(self.currentIndex())
        self.viewport().update()
        event.accept()

    def decode_data(self, bytearray):
        data = []
        item = {}
        ds = QDataStream(bytearray)

        while not ds.atEnd():
            row = ds.readInt32()
            column = ds.readInt32()
            map_items = ds.readInt32()

            for i in range(map_items):
                key = ds.readInt32()
                value = QVariant()
                ds >> value
                item[Qt.ItemDataRole(key)] = value
            
            data.append(item)
        
        return data

    def dropEvent(self, event):
        rect = self.rect()
        pos = event.pos()
        index = self.indexAt(pos)
        itemrect = self.visualRect(index)

        if index.row() < 0:
            dropindex = self.model().rowCount()

        elif (event.pos().y() - itemrect.y()) < itemrect.height()/2:
            dropindex = index.row()

        else:
            dropindex = index.row() + 1

        source = event.source()

        if isinstance(source, InputTreeView):
            index = source.currentIndex()
            obj = index.data(Qt.UserRole)

            if isinstance(obj, BaseReader):
                for k, track in enumerate(obj.tracks):
                    try:
                        name = track.name

                    except:
                        name = None

                    try:
                        lang = track.language

                    except:
                        lang = None

                    newtrack = self.output_file.trackclass(track, name=name, language=lang, container=self.output_file)
                    self.insertTrack(dropindex + k, newtrack)

                self.contentsChanged.emit()

            elif isinstance(obj, InputTrack):
                newtrack = self.output_file.trackclass(obj, container=self.output_file)
                self.insertTrack(dropindex, newtrack)
                self.contentsChanged.emit()

        elif event.source() == self:
            event.accept()
            index = self.currentIndex()
            self.moveTrack(index.row(), self._dropIndex)
            self.contentsChanged.emit()

        else:
            event.ignore()

        self.viewport().update()
        self._dropIndex = None

    def insertTrack(self, index, track):
        self.model().insertRow(index, track)
        #self.openPersistentEditor(self.model().index(index, 2))
        #self.openPersistentEditor(self.model().index(index, 3))
        self.contentsChanged.emit()

    def moveTrack(self, old_index, new_index):
        if new_index > old_index:
            I = range(old_index, new_index)

        else:
            I = range(new_index, old_index + 1)

        self.model().moveRow(old_index, new_index)
        self.contentsChanged.emit()

    def paintEvent(self, event):
        painter = QPainter(self.viewport())
        self.drawTree(painter, event.region())

        if self._dropIndex is not None:
            if self._dropIndex >= self.model().rowCount():
                rect = self.visualRect(self.model().index(self.model().rowCount() - 1, 0))
                y = rect.y() + rect.height()

            else:
                y = self.visualRect(self.model().index(self._dropIndex, 0)).y()

            w = self.viewport().width()
            painter.setPen(QPen(Qt.black, 2))
            painter.drawLine(0, y, w, y)

    def keyPressEvent(self, event):
        key = event.key()
        modifiers = event.modifiers()
        idx = self.currentIndex()
        row = idx.row()
        col = idx.column()
        model = self.model()

        selected = sorted(idx.row() for idx in self.selectionModel().selectedRows())

        if key == Qt.Key_Delete and modifiers == Qt.NoModifier and len(self.selectionModel().selectedRows()):
            self.askDeleteSelected()

        super().keyPressEvent(event)

    def askDeleteSelected(self):
        answer = QMessageBox.question(self, "Delete tracks", "Do you wish to delete the selected tracks? All encoder and settings associated with selected tracks will be lost!", QMessageBox.Yes | QMessageBox.No)

        if answer == QMessageBox.Yes:
            self.deleteSelected()

    def deleteSelected(self):
        selected = sorted(idx.row() for idx in self.selectionModel().selectedRows())

        for k, row in enumerate(selected):
            self.model().removeRow(row - k)

        self.contentsChanged.emit()

