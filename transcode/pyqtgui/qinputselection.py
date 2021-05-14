from .qinputtracklist import InputFilesRoot, FileTrackCol, LanguageCol, InputFmtCol
from .qfilterlistmodel import FiltersRoot
from .qfilterlistcols import FilterNameCol, SourceCol, FormatCol
from .qitemmodel import Node, ChildNodes, QItemModel
from PyQt5.QtWidgets import QTreeView, QToolButton, QWidgetAction, QMenu, QItemDelegate
from PyQt5.QtCore import QModelIndex, Qt, pyqtSignal
from PyQt5.QtGui import QIcon
from transcode.config.obj import InputFileList, FilterList
from transcode.containers.basereader import BaseReader, Track
from transcode.filters.base import BaseFilter


class InputSelectionRoot(Node):
    def _wrapChildren(self, children):
        return InputSelectionChildren.fromValues(children, self)


class InputSelectionChildren(ChildNodes):
    @staticmethod
    def _wrap(value):
        if value is None:
            return Node(value)

        elif isinstance(value, InputFileList):
            return InputFilesRoot(value)

        elif isinstance(value, FilterList):
            return FiltersRoot(value)


class ColumnUnion(object):
    def __init__(self, headerdisplay, incol, fcol, selectfunc=None, width=64):
        self.headerdisplay = headerdisplay
        self.width = width
        self.incol = incol
        self.fcol = fcol
        self.selectfunc = selectfunc

    def editdata(self, index, obj):
        if isinstance(obj, (BaseReader, Track)) and hasattr(self.incol, "editdata"):
            return self.incol.editdata(index, obj)

        if isinstance(obj, BaseFilter) and hasattr(self.fcol, "editdata"):
            return self.fcol.editdata(index, obj)

        return None

    def seteditdata(self, index, obj, value):
        if isinstance(obj, (BaseReader, Track)) and hasattr(self.incol, "editdata"):
            return self.incol.editdata(index, obj)

        if isinstance(obj, BaseFilter) and hasattr(self.fcol, "editdata"):
            return self.fcol.editdata(index, obj)

        return None

    def flags(self, index, obj):
        if obj is None:
            flags = Qt.ItemIsEnabled | Qt.ItemIsSelectable

        elif isinstance(obj, (BaseReader, Track)) and hasattr(self.incol, "flags"):
            if callable(self.incol.flags):
                flags = self.incol.flags(index, obj)

            else:
                flags = self.incol.flags

        elif isinstance(obj, BaseFilter) and hasattr(self.fcol, "flags"):
            if callable(self.fcol.flags):
                flags = self.fcol.flags(index, obj)

            else:
                flags = self.fcol.flags

        else:
            flags = Qt.ItemIsEnabled

        if obj is None:
            return flags | Qt.ItemIsSelectable

        if isinstance(obj, (Track, BaseFilter)) and (self.selectfunc is None or self.selectfunc(obj)):
            return flags | Qt.ItemIsSelectable | Qt.ItemIsEnabled

        return flags & ~Qt.ItemIsSelectable & ~Qt.ItemIsEnabled

    def display(self, index, obj):
        if obj is None:
            return "None"

        elif isinstance(obj, InputFileList):
            return "Input Files"

        elif isinstance(obj, FilterList):
            return "Filters"

        elif isinstance(obj, (BaseReader, Track)) and hasattr(self.incol, "display"):
            if callable(self.incol.display):
                return self.incol.display(index, obj)

            else:
                return self.incol.display

        elif isinstance(obj, BaseFilter) and hasattr(self.fcol, "display"):
            if callable(self.fcol.display):
                return self.fcol.display(index, obj)

            else:
                return self.fcol.display

    def icon(self, index, obj):
        if isinstance(obj, (BaseReader, Track)) and hasattr(self.incol, "icon"):
            if callable(self.incol.icon):
                return self.incol.icon(index, obj)

            else:
                return self.incol.icon

        elif isinstance(obj, BaseFilter) and hasattr(self.fcol, "icon"):
            if callable(self.fcol.icon):
                return self.fcol.icon(index, obj)

            else:
                return self.fcol.icon

    def tooltip(self, index, obj):
        if isinstance(obj, (BaseReader, Track)) and hasattr(self.incol, "tooltip"):
            if callable(self.incol.tooltip):
                return self.incol.tooltip(index, obj)

            else:
                return self.incol.tooltip

        elif isinstance(obj, BaseFilter) and hasattr(self.fcol, "tooltip"):
            if callable(self.fcol.tooltip):
                return self.fcol.tooltip(index, obj)

            else:
                return self.fcol.tooltip

    def sizehint(self, index, obj):
        if isinstance(obj, (BaseReader, Track)) and hasattr(self.incol, "sizehint"):
            if callable(self.incol.sizehint):
                return self.incol.sizehint(index, obj)

            else:
                return self.incol.sizehint

        elif isinstance(obj, BaseFilter) and hasattr(self.fcol, "sizehint"):
            if callable(self.fcol.sizehint):
                return self.fcol.sizehint(index, obj)

            else:
                return self.fcol.sizehint

    def bgcolor(self, index, obj):
        if isinstance(obj, (BaseReader, Track)) and hasattr(self.incol, "bgcolor"):
            if callable(self.incol.bgcolor):
                return self.incol.bgcolor(index, obj)

            else:
                return self.incol.bgcolor

        elif isinstance(obj, BaseFilter) and hasattr(self.fcol, "bgcolor"):
            if callable(self.fcol.bgcolor):
                return self.fcol.bgcolor(index, obj)

            else:
                return self.fcol.bgcolor

    def bgdata(self, index, obj):
        if isinstance(obj, (BaseReader, Track)) and hasattr(self.incol, "bgdata"):
            if callable(self.incol.bgdata):
                return self.incol.bgdata(index, obj)

            else:
                return self.incol.bgdata

        elif isinstance(obj, BaseFilter) and hasattr(self.fcol, "bgdata"):
            if callable(self.fcol.bgdata):
                return self.fcol.bgdata(index, obj)

            else:
                return self.fcol.bgdata

    def fgdata(self, index, obj):
        if isinstance(obj, (BaseReader, Track)) and hasattr(self.incol, "fgdata"):
            if callable(self.incol.fgdata):
                return self.incol.fgdata(index, obj)

            else:
                return self.incol.fgdata

        elif isinstance(obj, BaseFilter) and hasattr(self.fcol, "fgdata"):
            if callable(self.fcol.fgdata):
                return self.fcol.fgdata(index, obj)

            else:
                return self.fcol.fgdata

    def checkstate(self, index, obj):
        if isinstance(obj, (BaseReader, Track)) and hasattr(self.incol, "checkstate"):
            if callable(self.incol.checkstate):
                return self.incol.checkstate(index, obj)

            else:
                return self.incol.checkstate

        elif isinstance(obj, BaseFilter) and hasattr(self.fcol, "checkstate"):
            if callable(self.fcol.checkstate):
                return self.fcol.checkstate(index, obj)

            else:
                return self.fcol.checkstate

    def itemdata(self, index, obj):
        if isinstance(obj, (BaseReader, Track)) and hasattr(self.incol, "itemdata"):
            if callable(self.incol.itemdata):
                return self.incol.itemdata(index, obj)

            else:
                return self.incol.itemdata

        elif isinstance(obj, BaseFilter) and hasattr(self.fcol, "itemdata"):
            if callable(self.fcol.itemdata):
                return self.fcol.itemdata(index, obj)

            else:
                return self.fcol.itemdata

    def textalign(self, index, obj):
        if isinstance(obj, (BaseReader, Track)) and hasattr(self.incol, "textalign"):
            if callable(self.incol.textalign):
                return self.incol.textalign(index, obj)

            else:
                return self.incol.textalign

        elif isinstance(obj, BaseFilter) and hasattr(self.fcol, "textalign"):
            if callable(self.fcol.textalign):
                return self.fcol.textalign(index, obj)

            else:
                return self.fcol.textalign

    def font(self, index, obj):
        if isinstance(obj, (BaseReader, Track)) and hasattr(self.incol, "font"):
            if callable(self.incol.font):
                return self.incol.font(index, obj)

            else:
                return self.incol.font

        elif isinstance(obj, BaseFilter) and hasattr(self.fcol, "font"):
            if callable(self.fcol.font):
                return self.fcol.font(index, obj)

            else:
                return self.fcol.font


class QTreeSelection(QToolButton):
    currentIndexChanged = pyqtSignal(QModelIndex, QModelIndex)
    currentDataChanged = pyqtSignal(object)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setPopupMode(QToolButton.MenuButtonPopup)
        self.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)

        self.tree = QTreeView(self)
        self.tree.setMinimumWidth(640)
        self.tree.setSelectionMode(QTreeView.SingleSelection)
        self.tree.setSelectionBehavior(QTreeView.SelectRows)

        act = QWidgetAction(self)
        act.setDefaultWidget(self.tree)

        self.menu = QMenu(self)
        self.menu.addAction(act)
        self.setMenu(self.menu)
        self.clicked.connect(self.showMenu)

    def _currentIndexChanged(self, newindex, oldindex):
        self.menu.close()
        selected = newindex.sibling(newindex.row(), 0)

        display = selected.data(Qt.DisplayRole)
        icon = selected.data(Qt.DecorationRole)

        self.setText(display or "")
        self.setIcon(icon or QIcon())
        self.currentIndexChanged.emit(newindex, oldindex)
        self.currentDataChanged.emit(newindex.data(Qt.UserRole))

    def currentIndex(self):
        return self.tree.currentIndex()

    def currentData(self):
        return self.currentIndex().data(Qt.UserRole)

    def setCurrentIndex(self, index):
        return self.tree.setCurrentIndex(index)

    def model(self):
        return self.tree.model()

    def setModel(self, model):
        self.tree.setModel(model)
        self.tree.selectionModel().currentChanged.connect(self._currentIndexChanged)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Up, Qt.Key_Down) and not event.modifiers() & (Qt.ShiftModifier | Qt.AltModifier | Qt.ControlModifier):
            self.tree.keyPressEvent(event)

        return super().keyPressEvent(event)


class QInputSelection(QTreeSelection):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._func = None
        self.setSources(None, None)

    def setSources(self, input_files, filters):
        self.input_files = input_files
        self.filters = filters

        if input_files is not None:
            self.cols = [
                ColumnUnion("Input",
                            FileTrackCol(
                                input_files), FilterNameCol(filters),
                            width=256),
                ColumnUnion("Language",
                            LanguageCol(input_files), None, width=96),
                ColumnUnion("Source",
                            None, SourceCol(filters), width=96),
                ColumnUnion("Format",
                            InputFmtCol(input_files), FormatCol(filters), width=128),
            ]

            if filters:
                root = InputSelectionRoot([None, input_files, filters])

            else:
                root = InputSelectionRoot([None, input_files])

            model = QItemModel(root, self.cols)
            self.setModel(model)

            for k, col in enumerate(self.cols):
                if hasattr(col, "width"):
                    self.tree.setColumnWidth(k, col.width)

                col.selectfunc = self._func

            self.tree.expandAll()

        else:
            self.setModel(QItemModel(Node(None), []))
            self.cols = []

    def setSelectFunc(self, func):
        self._func = func

        for col in self.cols:
            col.selectfunc = func

        self.model().emitDataChanged()


class InputDelegate(QItemDelegate):
    def __init__(self, input_files, filters, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.input_files = input_files
        self.filters = filters

    def createEditor(self, parent, option, index):
        item = index.data(Qt.UserRole)

        try:
            item.source

        except AttributeError:
            return

        editor = QInputSelection(parent)
        editor.setSources(self.input_files, self.filters)
        return editor

    def setEditorData(self, editor, index):
        item = index.data(Qt.UserRole)

        if isinstance(item.source, Track) and item.source.container in self.input_files:
            file_index = self.input_files.index(item.source.container)
            track_index = item.source.track_index
            editor.setCurrentIndex(editor.model().index(
                1, 0).child(file_index, 0).child(track_index, 0))

        elif item.source in self.filters:
            filter_index = self.filters.index(item.source)
            editor.setCurrentIndex(
                editor.model().index(2, 0).child(filter_index, 0))

        if isinstance(item, BaseFilter):
            editor.setSelectFunc(item.isValidSource)

    def setModelData(self, editor, model, index):
        model.setData(index, editor.currentData(), Qt.EditRole)

    def updateEditorGeometry(self, editor, option, index):
        editor.setGeometry(option.rect)
