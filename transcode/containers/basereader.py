import transcode.util
import av
import threading
import time
import os
import sys
from transcode.util import cached
from collections import OrderedDict

class Track(object):
    from copy import deepcopy as copy

    def __init__(self):
        self.container = None
        self.pts = None

    @property
    def track_index(self):
        return self.container.tracks.index(self)

    def frameIndexFromPts(self, pts, dir="+"):
        return transcode.util.search(self.pts, pts, dir)

    def __reduce__(self):
        state = self.__getstate__()

        if state:
            return type(self), (), state

        return type(self), ()

    def __getstate__(self):
        state = OrderedDict()
        state["pts"] = self.pts
        return state

    def __setstate__(self, state):
        self.pts = state.get("pts")

    def keyIndexFromPts(self, pts, dir="-"):
        k = self.frameIndexFromPts(pts)
        pts = self.pts[k]
        return transcode.util.search(self.index[:, 0], pts, dir)

    @property
    def framecount(self):
        return len(self.pts)

    @cached
    def pts_time(self):
        return self.pts*float(self.time_base)

    @property
    def format(self):
        return

    @property
    def bitdepth(self):
        return

    @property
    def width(self):
        return

    @property
    def height(self):
        return

    @property
    def rate(self):
        return

    def iterFrames(self, start=0, end=None, whence="pts"):
        if whence == "framenumber":
            startindex = start
            startpts = self.pts[start]
            endindex = end and min(end, len(self.pts))

            try:
                endpts = end and self.pts[endindex]

            except IndexError:
                endpts = None

        elif whence == "pts":
            startindex = self.frameIndexFromPts(start, "-" if self.type is "audio" else "+")
            startpts = self.pts[startindex]

            try:
                endindex = end and self.frameIndexFromPts(end)
                endpts = end and self.pts[endindex]

            except IndexError:
                endindex = None
                endpts = None

        elif whence == "seconds":
            startindex = self.frameIndexFromPts(start/self.time_base, "-" if self.type is "audio" else "+")
            startpts = self.pts[startindex]

            try:
                endindex = end and self.frameIndexFromPts(end/self.time_base)
                endpts = end and self.pts[endindex]

            except IndexError:
                endindex = None
                endpts = None

        key_index = self.keyIndexFromPts(startpts)
        key_pts = self.index[key_index, 0]
        index = self.frameIndexFromPts(key_pts)

        packets = self.iterPackets(key_pts)

        decoder = av.CodecContext.create(self.codec, "r")

        iterpts1 = iter(self.pts[index:])
        iterpts2 = iter(self.pts[index+1:])

        try:
            if self.extradata:
                decoder.extradata = self.extradata

            framesdelivered = 0

            for packet in packets:
                avpacket = av.Packet(packet.data)
                avpacket.pts = packet.pts
                avpacket.time_base = self.time_base

                for frame, pts1, pts2 in zip(decoder.decode(avpacket), iterpts1, iterpts2):
                    if pts2 < startpts:
                        continue

                    if endpts is not None and pts1 >= endpts:
                        raise StopIteration

                    framesdelivered += 1
                    frame.pts = pts1

                    if self.type == "video":
                        frame.pict_type = 0

                    yield frame


            for frame, pts in zip(decoder.decode(), iterpts):
                if pts < startpts:
                    continue

                if endpts is not None and pts >= endpts:
                    raise StopIteration

                framesdelivered += 1
                frame.pts = pts
                frame.time_base = self.time_base
                yield frame

        finally:
            decoder.close()

    @property
    def duration(self):
        return (self.pts[-1] + self.durations[-1])*self.time_base

    @property
    def avgfps(self):
        return self.framecount/self.duration

    @property
    def defaultDuration(self):
        return None

class BaseReader(object):
    from copy import deepcopy as copy

    trackclass = Track

    def __init__(self, inputpath, tracks=None, config=None):
        self.inputpath = inputpath
        self.config = config
        self._open()

        if tracks is not None:
            self.tracks = tracks

        else:
            self._populatetracks()
            #self.tracks = []
            #self.scan()

    def _open(self):
        raise NotImplementedError(f"{self.__class__.__name__}._open not implemented.")

    def _populatetracks(self):
        raise NotImplementedError(f"{self.__class__.__name__}._populatetracks not implemented.")

    def __reduce__(self):
        state = self.__getstate__()
        return self.__class__, (self.inputpath,), state, iter(self.tracks)

    def __getstate__(self):
        state = OrderedDict()
        #state["inputpath"] = self.inputpath
        #state["tracks"] = self.tracks
        return state

    def __setstate__(self, state):
        pass

        #self.tracks = state.get("tracks", [])

        #for track in self.tracks:
            #track.container = self

    def append(self, track):
        track.container = self
        self.tracks.append(track)

    def insert(self, index, track):
        self.tracks.insert(index, track)

    def extend(self, tracks):
        for track in tracks:
            track.container = self

        self.tracks.extend(tracks)

    def clear(self):
        self.tracks.clear()

    @property
    def inputpathrel(self):
        """Input file path relative to config path."""
        if self.config:
            relpath = os.path.relpath(self.inputpath, self.config.workingdir)

            if relpath.startswith("../"):
                return self.inputpath

            else:
                return relpath

        return self.inputpath

    @inputpathrel.setter
    def inputpathrel(self, value):
        if self.config:
            self.inputpath = os.path.join(self.config.workingdir, value)

        else:
            self.inputpath = value

    @property
    def inputpathabs(self):
        """Input file absolute path."""
        return os.path.abspath(self.inputpath)


