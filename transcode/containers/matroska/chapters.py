import matroska.chapters
import transcode.util
from collections import OrderedDict, UserList

class ChapterDisplay(object):
    from copy import deepcopy as copy

    def __init__(self, string, languages=["eng"], langIETF=[], countries=["us"]):
        self.string = string
        self.languages = languages.copy()
        self.langIETF = langIETF.copy()
        self.countries = countries.copy()

    def prepare(self, logfile=None):
        print(f"        Name: {self.string}", file=logfile)
        print(f"            Lanugages: {', '.join(self.languages)}", file=logfile)
        print(f"            Countries: {', '.join(self.countries)}", file=logfile)
        return matroska.chapters.ChapterDisplay(self.string, self.languages,
                                                self.langIETF, self.countries)

    def __reduce__(self):
        return self.__class__, (self.string,), self.__getstate__()

    def __getstate__(self):
        state = {}
        state["languages"] = self.languages
        state["langIETF"] = self.langIETF
        state["countries"] = self.countries
        return state

    def __setstate__(self, state):
        self.languages = state.get("languages", ["eng"])
        self.langIETF = state.get("langIETF", [])
        self.countries = state.get("countries", ["us"])

class ChapterAtom(object):
    from copy import deepcopy as copy

    def __init__(self, UID, startFrame, endFrame=None, displays=[], hidden=False, enabled=True, segmentUID=None,
                 segmentEditionUID=None, physicalEquiv=None, tracks=None, next=None, prev=None, parent=None):
        self.UID = UID
        self.startFrame = startFrame
        self.endFrame = endFrame
        self.displays = displays.copy()
        self.hidden = hidden
        self.enabled = enabled
        self.segmentUID = segmentUID
        self.segmentEditionUID = segmentEditionUID
        self.physicalEquiv = physicalEquiv
        self.tracks = tracks
        self.next = next
        self.prev = prev
        self.parent = parent

    @property
    def mkvfile(self):
        if self.parent:
            return self.parent.parent

    @property
    def config(self):
        if self.mkvfile:
            return self.mkvfile.config

    @property
    def segment(self):
        if self.segmentUID and self.config:
            for outputfile in self.config.output_files:
                if outputfile.segmentUID == self.segmentUID:
                    return outputfile

            return

        return self.mkvfile

    @property
    def timeStart(self):
        if self.segment and self.segment.vtrack:
            if self.segment.vtrack.filters:
                k = -1
                n = self.startFrame

                while k < 0:
                    k = self.segment.vtrack.filters.indexMap[n]
                    n += 1

            else:
                k = self.startFrame

            return self.parent.parent.vtrack.pts[k]

    @property
    def timeEnd(self):
        if self.parent:
            if self.parent.ordered and self.segment and self.segment.vtrack:
                if self.segment.vtrack.filters:
                    k = -1
                    n = self.endFrame

                    while k < 0:
                        k = self.segment.vtrack.filters.indexMap[n]
                        n += 1

                else:
                    k = self.endFrame

                return self.segment.vtrack.pts[self.endFrame]

            elif self.next:
                return self.next.timeStart

            elif self.segment and self.segment.vtrack:
                return int(self.segment.vtrack.duration/self.segment.vtrack.time_base)

    def prepare(self, logfile=None):
        flagstrings = [f"UID {self.UID}"]

        if self.enabled:
            flagstrings.append("Enabled")

        if self.hidden:
            flagstrings.append("Hidden")

        m, ms = divmod(self.timeStart, 60*10**9)
        s1 = ms/10**9
        h1, m1 = divmod(m, 60)
        m, ms = divmod(self.timeEnd, 60*10**9)
        s2 = ms/10**9
        h2, m2 = divmod(m, 60)
        print(f"    Chapter {self.parent.index(self) + 1}: {', '.join(flagstrings)}", file=logfile)
        ebml = matroska.chapters.ChapterAtom(self.UID, self.timeStart, self.timeEnd, self.hidden, self.enabled,
                chapterSegmentUID=self.segmentUID, chapterSegmentEditionUID=self.segmentEditionUID,
                chapterTrack=self.tracks, chapterDisplays=[display.prepare(logfile) for display in self.displays])
        print(f"        Time: {h1}:{m1:02d}:{s1:06.3f} — {h2}:{m2:02d}:{s2:06.3f}", file=logfile)
        return ebml

    def __reduce__(self):
        return self.__class__, (self.UID, self.startFrame), self.__getstate__()

    def __getstate__(self):
        state = OrderedDict()

        if self.endFrame is not None:
            state["endFrame"] = self.endFrame

        if self.displays is not None:
            state["displays"] = self.displays

        if self.hidden is not None:
            state["hidden"] = self.hidden

        if self.enabled is not None:
            state["enabled"] = self.enabled

        if self.segmentUID is not None:
            state["segmentUID"] = self.segmentUID

        if self.segmentEditionUID is not None:
            state["segmentEditionUID"] = self.segmentEditionUID

        if self.physicalEquiv is not None:
            state["physicalEquiv"] = self.physicalEquiv

        if self.tracks is not None:
            state["tracks"] = self.tracks

        return state

    def __setstate__(self, state):
        self.endFrame = state.get("endFrame")
        self.displays = state.get("displays", [])
        self.hidden = state.get("hidden", False)
        self.enabled = state.get("enabled", True)
        self.segmentUID = state.get("segmentUID")
        self.segmentEditionUID = state.get("segmentEditionUID")
        self.physicalEquiv = state.get("physicalEquiv")
        self.tracks = state.get("tracks")

class EditionEntry(transcode.util.llist):
    def __init__(self, chapters=[], UID=None, hidden=False, default=False, ordered=False, parent=None):
        self.UID = UID
        self.hidden = hidden
        self.default = default
        self.ordered = ordered
        self.parent = parent
        super().__init__(chapters)

    def insert(self, index, chapter):
        super().insert(index, chapter)

    def __getstate__(self):
        state = OrderedDict()
        state["UID"] = self.UID
        state["hidden"] = self.hidden
        state["default"] = self.default
        state["ordered"] = self.ordered
        return state

    def __setstate__(self, state):
        self.UID = state.get("UID")
        self.hidden = state.get("hidden", False)
        self.default = state.get("default", False)
        self.ordered = state.get("ordered", False)

    def prepare(self, logfile=None):
        flagstrings = []

        if self.default:
            flagstrings.append("Default")

        if self.hidden:
            flagstrings.append("Hidden")

        if self.ordered:
            flagstrings.append("Ordered")

        if len(flagstrings):
            print(f"Edition Entry {self.UID} ({', '.join(flagstrings)})", file=logfile)

        else:
            print(f"Edition Entry {self.UID}", file=logfile)
        
        return matroska.chapters.EditionEntry(self.UID, self.hidden, self.default, [chapter.prepare(logfile) for chapter in self], self.ordered)

class Editions(transcode.util.ChildList):
    def prepare(self, logfile=None):
        print("--- Chapters ---", file=logfile)
        return matroska.chapters.Chapters([edition.prepare(logfile) for edition in self])
