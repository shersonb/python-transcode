from transcode.containers import basereader
import ass
import numpy
import av
from fractions import Fraction as QQ
import os
from itertools import islice
from transcode.util import Packet


class Track(basereader.Track):
    def __getstate__(self):
        state = super().__getstate__() or OrderedDict()
        state["index"] = self.index
        state["sizes"] = self.sizes
        state["durations"] = self.durations
        return state

    def __setstate__(self, state):
        self.index = state.get("index")
        super().__setstate__(state)

    @property
    def extradata(self):
        sections = []

        for head, section in self.container.assfile.sections.items():
            if head == "Events":
                sections.append(
                    "\n".join([f"[{head}]", ", ".join(section.field_order)]))
                break

            sections.append("\n".join(section.dump()))

        return "\n\n".join(sections).encode("utf8")

    @property
    def type(self):
        return "subtitle"

    @property
    def codec(self):
        return "ass"

    @property
    def time_base(self):
        return self.container.time_base

    def iterPackets(self, start=0, whence="pts"):
        if whence == "pts":
            start = self.frameIndexFromPts(start)

        if whence == "seconds":
            start = self.frameIndexFromPts(int(start/self.time_base))

        elif whence == "framenumber":
            pass

        fields = [field for field in self.container.assfile.events.field_order if field not in (
            "Start", "End")]

        for k, event in enumerate(self.container.assfile.events[start:], start):
            data = f"{k},{event.dump(fields)}".encode("utf8")
            yield Packet(data=data, pts=int(event.start.total_seconds()/self.time_base),
                         duration=int(
                             (event.end - event.start).total_seconds()/self.time_base),
                         keyframe=True, time_base=self.time_base)

    def iterFrames(self, start=0, end=None, whence="pts"):
        if whence == "pts":
            start = self.frameIndexFromPts(start)

            try:
                end = end and self.frameIndexFromPts(end)

            except IndexError:
                end = None

        elif whence == "seconds":
            start = self.frameIndexFromPts(start/self.time_base)

            try:
                end = end and self.frameIndexFromPts(end/self.time_base)

            except IndexError:
                end = None

        return islice(self.container.assfile.events, start, end)

    @property
    def pts(self):
        return numpy.int0([event.start.total_seconds()*self.time_base.denominator/self.time_base.numerator
                           for event in self.container.assfile.events])

    @pts.setter
    def pts(self, value):
        pass

    @property
    def sizes(self):
        fields = [field for field in self.container.assfile.events.field_order if field not in (
            "Start", "End")]
        return numpy.int0([len(f"{k+1},{event.dump(fields)}".encode("utf8"))
                           for k, event in enumerate(self.container.assfile.events)])

    @sizes.setter
    def sizes(self, value):
        pass

    @property
    def durations(self):
        return numpy.int0([(event.end.total_seconds() - event.start.total_seconds())*self.time_base.denominator/self.time_base.numerator
                           for event in self.container.assfile.events])

    @durations.setter
    def durations(self, value):
        pass


class SubstationAlphaReader(basereader.BaseReader):
    trackclass = Track
    extensions = (".ass", ".ssa", ".assa")
    fmtname = "Substation Alpha/Advanced Substation Alpha"

    def _open(self):
        self.assfile = ass.document.Document.parse_file(
            open(self.inputpath, "r", encoding="utf_8_sig"))

    def _populatetracks(self):
        self.tracks = [Track()]
        self.tracks[0].container = self
        self.scan()

    def scan(self, notifystart=None, notifyprogress=None, notifyfinish=None):
        track = self.tracks[0]
        track.index = None

    @property
    def time_base(self):
        return QQ(1, 100)
