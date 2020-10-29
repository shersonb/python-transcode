from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon, QBrush, QFont
from PyQt5.QtWidgets import QMenu, QAction
from functools import partial
from ..filters.base import BaseFilter
from transcode.containers.basereader import Track


class BaseFilterCol(object):
    textalign = Qt.AlignLeft | Qt.AlignVCenter
    bgdata = QBrush()
    itemDelegate = None
    font = QFont("DejaVu Serif", 8)

    def __init__(self, filters, attrname=None, noselect=[]):
        self.filters = filters
        self.attrname = attrname
        self.noselect = noselect

    def editdata(self, index, obj):
        return getattr(obj, self.attrname)

    def seteditdata(self, index, obj, data):
        setattr(obj, self.attrname, data)

    def flags(self, index, obj):
        if obj in self.noselect:
            return Qt.ItemIsEnabled

        return Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsDragEnabled

    def contextmenu(self, index, obj):
        return partial(self.createContextMenu, obj=obj, index=index)

    def createContextMenu(self, table, index, obj):
        menu = QMenu(table)
        input_files = self.filters.config.input_files

        editfilter = QAction(f"Configure filter...", table,
                             triggered=partial(obj.QtDlg, inputFiles=input_files,
                                               availableFilters=self.filters))

        if not hasattr(obj, "QtDlgClass") or obj.QtDlgClass is None:
            editfilter.setEnabled(False)

        menu.addAction(editfilter)

        return menu


class FilterNameCol(BaseFilterCol):
    headerdisplay = "Filter"
    width = 240
    flags = Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsDragEnabled | Qt.ItemIsEditable

    def __init__(self, filters):
        super().__init__(filters, "name")

    def editdata(self, index, obj):
        if obj is None:
            return None

        return super().editdata(index, obj)

    def display(self, index, obj):
        k = self.filters.index(obj)

        if obj is None or not obj.name:
            return f"{k}: {obj.__class__.__name__}"

        __name__ = obj.__name__
        return f"{k}: {obj.name} ({obj.__class__.__name__})"

    def tooltip(self, index, obj):
        return f"{obj.__class__.__module__}.{obj.__class__.__name__}"

    def icon(self, index, obj):
        if not hasattr(obj, "type"):
            return

        if obj.type == "video":
            return QIcon.fromTheme("video-x-generic")

        if obj.type == "audio":
            return QIcon.fromTheme("audio-x-generic")

        if obj.type == "subtitle":
            return QIcon.fromTheme("text-x-generic")


class SourceCol(BaseFilterCol):
    headerdisplay = "Source"
    width = 96
    flags = Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsDragEnabled

    def __init__(self, filters):
        super().__init__(filters, "source")

    def display(self, index, obj):
        if isinstance(obj, BaseFilter):
            try:
                source = obj.source

            except AttributeError:
                return ""

            if isinstance(source, Track):

                return f"input:{self.filters.config.input_files.index(source.container)}:{source.track_index} ()"

            elif isinstance(source, BaseFilter) and source in self.filters:
                name = source.name or source.__class__.__name__
                return f"filters:{self.filters.index(source)} ({name})"

        return ""

    def tooltip(self, index, obj):
        return f"{obj.__class__.__module__}.{obj.__class__.__name__}"


class OptionsCol(BaseFilterCol):
    headerdisplay = "Options"
    width = 256
    flags = Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsDragEnabled

    def __init__(self, filters):
        super().__init__(filters, None)

    def display(self, index, obj):
        options = obj.__getstate__()
        optlist = []

        for key, value in options.items():
            if key in ("prev", "source"):
                continue

            if isinstance(value, Track):
                file_index = self.filters.config.input_files.index(
                    value.container)
                optlist.append(f"{key}={file_index}:{value.track_index}")

            elif isinstance(value, BaseFilter) and value in self.filters:
                filter_index = self.filters.index(value)
                optlist.append(f"{key}=filters:{filter_index}")

            elif isinstance(value, float):
                optlist.append(f"{key}={value:.9f}")

            else:
                optlist.append(f"{key}={value}")

        return ", ".join(optlist)

    tooltip = display


class FormatCol(BaseFilterCol):
    headerdisplay = "Format"
    width = 256
    flags = Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsDragEnabled

    def __init__(self, filters):
        super().__init__(filters, "format")

    def display(self, index, obj):
        if not hasattr(obj, "type"):
            return

        if obj.type == "video":
            fmt = []

            if obj.width is not None and obj.height is not None:
                fmt.append(f"{obj.width}×{obj.height}")

            if obj.sar is not None:
                fmt.append(f"sar: {obj.sar}")

            if obj.format is not None:
                fmt.append(f"{obj.format}")

            if obj.rate is not None:
                fmt.append(f"{obj.rate} fps")

            return ", ".join(fmt)

        if obj.type == "audio":
            fmt = []

            if obj.rate is not None:
                fmt.append(f"{obj.rate} kHz")

            if obj.channels is not None:
                fmt.append(f"{obj.channels} channels")

            if obj.layout is not None:
                fmt.append(f"{obj.layout}")

            if obj.format is not None:
                fmt.append(f"{obj.format}")

            return ", ".join(fmt)


class DurationCol(BaseFilterCol):
    headerdisplay = "Duration"
    width = 128
    flags = Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsDragEnabled

    def __init__(self, filters):
        super().__init__(filters, "format")

    def display(self, index, obj):
        if isinstance(obj.duration, (int, float)):
            m, s = divmod(obj.duration, 60)
            h, m = divmod(int(m), 60)
            return f"{h}:{m:02d}:{s:012.9f}"
