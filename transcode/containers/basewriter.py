from ..util import (search, h, WorkaheadIterator, WeakRefProperty,
                    SourceError, FileAccessDeniedError, EncoderError)
import threading
import time
import os
import sys
import traceback
from itertools import zip_longest
import json
import numpy
from collections import OrderedDict, UserList
from ebml.ndarray import EBMLNDArray
import abc
from fractions import Fraction as QQ
from copy import deepcopy
from ..encoders import vencoders, sencoders, aencoders
from transcode.avarrays import toNDArray, toAFrame
import socket


class TrackStats(EBMLNDArray):
    ebmlID = b"\x19\x14\xdc\x87"


class TrackList(UserList):
    parent = WeakRefProperty("parent")

    def __init__(self, items=[], container=None):
        self.data = list(items)
        self.container = container

    @property
    def container(self):
        return self._container

    @container.setter
    def container(self, value):
        for item in self:
            item.container = value

        self._container = value

    def append(self, item):
        item.container = self.container
        super().append(item)

    def insert(self, index, item):
        item.container = self.container
        super().insert(index, item)

    def extend(self, items):
        k = len(self)
        super().extend(items)
        for item in self[k:]:
            item.container = self.container

    def __reduce__(self):
        state = self.__getstate__()

        if state:
            return self.__class__, (), state, iter(self)

        return self.__class__, (), None, iter(self)

    def __getstate__(self):
        return


class Track(abc.ABC):
    """Base class for output tracks."""
    from copy import deepcopy as copy

    parent = WeakRefProperty("parent")

    def __init__(self, source, encoder=None, filters=None,
                 name=None, language=None, delay=0, container=None):
        self.source = source
        self.encoder = encoder
        self.name = name
        self.language = language
        self.encoderContext = None
        self.filters = filters
        self.delay = delay

        self.container = container
        self._packets = None
        self._sizes = []
        self.sizeStats = None

    def __reduce__(self):
        state = self.__getstate__()
        if state:
            return type(self), (self.source,), state

        return type(self), (self.source,)

    def __getstate__(self):
        state = OrderedDict()

        if self.encoder:
            state["encoder"] = self.encoder

        if self.filters:
            state["filters"] = self.filters

        if self.name:
            state["name"] = self.name

        if self.language:
            state["language"] = self.language

        if self.delay:
            state["delay"] = self.delay

        return state

    def __setstate__(self, state):
        self.encoder = state.get("encoder")
        self.filters = state.get("filters")
        self.name = state.get("name")
        self.language = state.get("language")
        self.delay = state.get("delay", 0)

    def __deepcopy__(self, memo):
        """
        We want to keep the original reference to self.source.
        """
        memo.update({
            id(self.source): self.source,
        })

        reduced = self.__reduce__()

        if len(reduced) == 2:
            cls, args = reduced
            state = items = dictitems = None

        elif len(reduced) == 3:
            cls, args, state = reduced
            items = dictitems = None

        if len(reduced) == 4:
            cls, args, state, items = reduced
            dictitems = None

        if len(reduced) == 5:
            cls, args, state, items, dictitems = reduced

        new = cls(*(deepcopy(arg, memo) for arg in args))

        if state is not None:
            new.__setstate__(deepcopy(state, memo))

        if items is not None:
            new.extend(deepcopy(item, memo) for item in items)

        if dictitems is not None:
            new.update(deepcopy(dictitems, memo))

        return new

    @property
    def filters(self):
        return self._filters

    @filters.setter
    def filters(self, value):
        self._filters = value

        if value is not None:
            value.prev = self.source

    source = WeakRefProperty("source")

    @source.setter
    def source(self, value):
        try:
            self.filters.prev = value

        except AttributeError:
            pass

        return value

    @property
    def time_base(self):
        return self.container.time_base

    @property
    def extradata(self):
        if self.encoderContext:
            return self.encoderContext.extradata

        return self.source.extradata

    @property
    def bitrate(self):
        if self.encoder:
            return self.encoder.bitrate

        try:
            return self.source.bitrate

        except AttributeError:
            return

    def _iterPackets(self, packets, duration=None, logfile=None):
        hasPacketHook = hasattr(self, "_iterPacketHook") and callable(
            self._iterPacketHook)
        self._sizes = []
        track_index = self.track_index
        exit = False

        try:
            try:
                for packet in packets:
                    packet.track_index = track_index
                    packet.pts += int(self.delay/self.time_base)

                    if hasPacketHook:
                        packet = self._iterPacketHook(packet)

                    if (duration is not None
                            and packet.keyframe
                            and packet.pts >= duration/self.time_base):
                        break

                    yield packet

            except GeneratorExit:
                exit = True

            except Exception as exc:
                yield exc

            else:
                try:
                    self.sizeStats = numpy.concatenate(
                        (self.sizeStats, (self._sizes,)))

                except Exception:
                    self.sizeStats = numpy.array((self._sizes,))

            if not exit:
                while True:
                    yield None

        finally:
            if sum(self._sizes) > 1024:
                print(
                    f"Track {self.track_index}: "
                    f"{len(self._sizes):,d} packets, {h(sum(self._sizes))} "
                    f"({sum(self._sizes):,d} bytes)", file=logfile)

            else:
                print(
                    f"Track {self.track_index}: "
                    f"{len(self._sizes):,d} packets, "
                    f"{sum(self._sizes):,d} bytes", file=logfile)

            packets.close()

    def _prepare(self, duration=None, logfile=None, **kwargs):
        if self.type == "video":
            print(f"Track {self.track_index}: Video, "
                  f"{self.width}x{self.height}, "
                  f"{1/self.defaultDuration/self.time_base} fps, "
                  f"{self.format}", file=logfile)

        elif self.type == "audio":
            print(
                f"Track {self.track_index}: Audio, {self.rate}Hz, "
                f"{self.layout}, {self.format}", file=logfile)

        elif self.type == "subtitle":
            print(f"Track {self.track_index}: Subtitles", file=logfile)

        if self.name:
            print(f"    Name: {self.name}", file=logfile)

        if self.language:
            print(f"    Language: {self.language}", file=logfile)

        if logfile:
            logfile.flush()

        if self.encoder:
            try:
                packets = self.openencoder(
                    duration=duration, logfile=logfile, **kwargs)

            except Exception:
                print("FAILED to open encoder.", file=logfile)
                raise

        else:
            packets = self.openpackets(duration=duration, logfile=logfile)

        self._prepareentry(packets=packets, logfile=logfile)
        packets = WorkaheadIterator(packets, 6)

        if self.encoder:
            return self._iterPackets(packets, logfile=logfile)

        return self._iterPackets(packets, duration=duration, logfile=logfile)

    @abc.abstractmethod
    def _prepareentry(self, packets, logfile=None, **kwargs):
        """
        Prepares track entry, specifically handing the private codec data and
        adding track entry to container headers.
        """

    @property
    def type(self):
        source = self.source

        if source is not None:
            return source.type

    @property
    def width(self):
        if self.encoder and self.filters:
            return self.filters.width

        source = self.source

        if source is not None:
            return source.width

    @property
    def height(self):
        if self.encoder and self.filters:
            return self.filters.height

        source = self.source

        if source is not None:
            return source.height

    @property
    def rate(self):
        if self.encoder and self.filters:
            return self.filters.rate

        source = self.source

        if source is not None:
            return source.rate

    @property
    def channels(self):
        if self.encoder and self.filters:
            return self.filters.channels

        source = self.source

        if source is not None:
            return source.channels

    @property
    def layout(self):
        source = self.source

        if self.encoder and self.filters and self.filters.layout:
            return self.filters.layout

        elif source is not None and source.layout:
            return self.source.layout

        elif self.channels == 8:
            return f"{self.channels - 1}.1"

        elif self.channels == 6:
            return f"{self.channels - 1}.1(side)"

        elif self.channels == 2:
            return "stereo"

        elif self.channels == 1:
            return "mono"

    @property
    def sar(self):
        if self.encoder and self.filters:
            return self.filters.sar

        source = self.source

        if source is not None:
            return source.sar

    @property
    def dar(self):
        if self.encoder and self.filters:
            return self.filters.dar

        source = self.source

        if source is not None:
            return source.dar

    @property
    def defaultDuration(self):
        if self.encoder:
            if self.type == "audio":
                if self.codec in ("aac", "libfdk_aac"):
                    return QQ(1024, self.rate)/self.time_base

                elif self.codec == "ac3":
                    return QQ(1536, self.rate)/self.time_base

                elif self.codec == "dca":
                    return QQ(512, self.rate)/self.time_base

                elif self.codec == "truehd":
                    return QQ(40, self.rate)/self.time_base

            elif self.filters and self.filters.defaultDuration is not None:
                return (self.filters.defaultDuration
                        * self.filters.time_base/self.time_base)

        source = self.source

        if source is not None and source.defaultDuration is not None:
            return source.defaultDuration*source.time_base/self.time_base

    @property
    def duration(self):
        if self.encoder and self.filters:
            return self.filters.duration

        source = self.source

        if source is not None:
            return source.duration

    @property
    def bitdepth(self):
        if self.encoder:
            if self.encoder.bitdepth is not None:
                return self.encoder.bitdepth

            elif self.filters and self.filters.bitdepth:
                return self.filters.bitdepth

        source = self.source

        if source is not None:
            return source.bitdepth

    @property
    def format(self):
        if self.encoder:
            if self.encoder.format is not None:
                return self.encoder.format

            elif self.filters and self.filters.format:
                return self.filters.format

        source = self.source

        if source is not None:
            return source.format

    @property
    def avgfps(self):
        if self.framecount is not None and self.duration:
            return self.framecount/self.duration

    @property
    def track_index(self):
        if self.container is not None:
            return self.container.tracks.index(self)

    @property
    def codec(self):
        if self.encoder:
            return self.encoder.codec

        source = self.source

        if source is not None:
            return source.codec

    def _iterFrames(self, duration=None, logfile=None):
        source = self.source

        if self.filters:
            if duration is not None:
                frames = self.filters.iterFrames(
                    end=int(duration/self.filters.time_base), whence="pts")

            else:
                frames = self.filters.iterFrames()

            rate = self.filters.rate

        elif source is not None:
            if duration is not None:
                frames = self.source.iterFrames(
                    end=int(duration/self.source.time_base), whence="pts")

            else:
                frames = self.source.iterFrames()

            rate = self.source.rate

        if self.type == "audio":
            samples = 0
            N = int(rate*duration + 0.5)

            for frame in frames:
                self.container._checkpause()

                if samples + frame.samples == N:
                    yield frame
                    break

                elif samples + frame.samples > N:
                    pts = frame.pts
                    time_base = frame.time_base
                    A = toNDArray(frame)
                    frame = toAFrame(A[:N - samples], frame.layout.name)
                    frame.pts = pts
                    frame.time_base = time_base
                    frame.rate = rate
                    yield frame
                    break

                yield frame
                samples += frame.samples

        else:
            for frame in frames:
                self.container._checkpause()

                if (duration is not None
                        and frame.pts*frame.time_base < duration):
                    yield frame

    def openencoder(self, duration=None, logfile=None, **kwargs):
        frames = self._iterFrames(duration - self.delay, logfile)
        print(f"    Codec: {self.codec}", file=logfile)

        if self.type == "video":
            kwargs.update(width=self.width, height=self.height,
                          sample_aspect_ratio=self.sar,
                          rate=1/self.defaultDuration/self.time_base)

            if self.format:
                kwargs.update(pix_fmt=self.format)

        if self.type == "audio":
            kwargs.update(rate=self.rate, layout=self.layout)

            if self.format:
                kwargs.update(format=self.format)

        packets = self.encoder.create(
            frames, logfile=logfile, time_base=self.time_base, **kwargs)
        packets.open()
        return packets

    def openpackets(self, duration=None, logfile=None):
        print(f"    Codec: {self.codec} (copy)", file=logfile)
        packets = self.source.iterPackets()

        if (hasattr(self.source, "defaultDuration")
                and self.source.defaultDuration):
            return WorkaheadIterator(
                packets,
                int(10/self.source.defaultDuration/self.source.time_base) + 1)

        return WorkaheadIterator(packets)

    @property
    def framecount(self):
        if isinstance(self.pts, numpy.ndarray):
            if self.encoder is not None and self.codec == "libfdk_aac":
                return len(self.pts) + 2

            return len(self.pts)

    @property
    def durations(self):
        if (self.encoder
                and self.type == "audio"
                and self.codec in ("aac", "libfdk_aac",
                                   "ac3", "dca", "truehd")):
            return int(self.defaultDuration)*numpy.ones(self.framecount,
                                                        dtype=numpy.int0)

        elif self.encoder and self.filters:
            return numpy.int0(self.filters.durations
                              * float(self.filters.time_base/self.time_base))

        if (hasattr(self.source, "durations")
                and self.source.durations is not None
                and self.source.time_base is not None
                and self.time_base is not None):
            return numpy.int0(self.source.durations
                              * float(self.source.time_base/self.time_base))

    @property
    def pts(self):
        if self.type == "audio":
            pts = numpy.int0(
                numpy.arange(self.delay/self.time_base,
                             min(self.duration + self.delay,
                                 self.container.duration)/self.time_base,
                             self.defaultDuration, dtype=numpy.float64))

        elif self.encoder and self.filters:
            pts = numpy.int0(self.filters.pts *
                             float(self.filters.time_base/self.time_base))

        elif (self.source is not None
              and self.source.time_base is not None
              and self.time_base is not None):
            pts = numpy.int0(
                self.source.pts*float(self.source.time_base/self.time_base))

        else:
            return numpy.zeros((0,), dtype=numpy.int0)

        try:
            n = search(pts, self.container.duration/self.time_base, dir="+")
            return pts[:n]

        except Exception:
            return pts

    def frameIndexFromPts(self, pts, dir="+"):
        return search(self.pts, pts, dir)

    @property
    def dependencies(self):
        dep = set()

        if self.filters is not None:
            dep.update(self.filters.dependencies)

        if hasattr(self.source, "dependencies"):
            dep.update(self.source.dependencies)

        return dep

    def validate(self):
        exceptions = []

        if self.source is None:
            exceptions.append(SourceError("No source provided.", self))

        else:
            if not self.source.canIterPackets and self.encoder is None:
                exceptions.append(EncoderError(
                    "Encoder must be specified for source that "
                    "cannot provide packets.", self))

            if self.encoder is not None:
                if (self.encoder.codec in vencoders and
                        self.source.type != "video"):
                    exceptions.append(EncoderError(
                        "Video encoder not compatible with "
                        f"{self.source.type} track.", self))

                elif (self.encoder.codec in aencoders
                      and self.source.type != "audio"):
                    exceptions.append(EncoderError(
                        "Audio encoder not compatible with "
                        f"{self.source.type} track.", self))

                elif (self.encoder.codec in sencoders
                      and self.source.type != "subtitle"):
                    exceptions.append(EncoderError(
                        "Subtitle encoder not compatible with "
                        f"{self.source.type} track.", self))

        if self.filters is not None:
            exceptions.extend(
                exc for f in self.filters for exc in f.validate())

        return exceptions


class BaseWriter(abc.ABC):
    """
    Base class for output containers.

    Methods self._preparefile, self._mux, and self._finalize MUST be
    implemented, while self._excepthandler MAY be implemented, but is not
    required.

    Class variable 'trackclass' SHOULD be set to an accompanying subclass
    of 'Track.'

    Class variable 'fmtname' MAY be set to identify the name of the
    the container format.

    Class variable 'extensions' MAY be set to identify file extensions used by
    the container format.

    When subclassing, keep the following function/method call order in mind:

    self.transcode()
        ├─ self.loadOverhead() (populates self.vtrack.sizeStats
        |          if data is available)
        ├─ notifystats(self.vtrack.sizeStats) (if notifystats is provided
        │          and self.track is not None)
        ├─ self.open()
        │   └─ self._open() (OVERRIDE this method in subclass)
        ├─ self._iterators = self._prepare()
        │   ├─ self._preparefile() (OVERRIDE this method in subclass)
        │   └─ self._preparetracks()
        │       ├─ self.bitrateFromTargetSize() (if self.vtrack is not None)
        │       └─ track._prepare() (for track in self.tracks,
        │           │       NOTE: notifyvencode is passed down to
        │           │       this method if track == self.vtrack)
        │           ├─ track._prepareentry() (OVERRIDE this method in subclass
        │           │       of Track)
        │           ├─ packets = track.openencoder() (if track.encoder is not
        │           │       None, handles notifyvencode if provided)
        │           ├─ packets = track.openpackets() (if track.encoder is None)
        │           └─ track._iterPackets(packets)
        ├─ self._multiplex()
        │   └─ for packet in self._iterPackets():
        │       ├─ self._checkpause(notifypause)
        │       ├─ self._mux(packet) (OVERRIDE in subclass)
        │       └─ notifymux(packet) (if notifymux is provided)
        ├─ self._closepackets(self._iterators)
        │   └─ iterator.close() (for iterator in self._iterators)
        └─ self._wrapup()
            ├─ if self.multiplex() completes without interruption:
            │   ├─ self._finalize() (if self.multiplex() completes without
            │   │           interruption, OVERRIDE this method in subclass)
            │   ├─ self.saveOverhead() (if self.multiplex() completes without
            |   |           interruption)
            │   └─ notifyfinish() (if self.multiplex() completes without
            │          interruption and notifyfinish is provided)
            └─ if self.multiplex() is interrupted with either
                │          self.stopTranscode() or KeyboardInterrupt:
                └─ notifycancelled() (if notifycancelled is provided)

    If an exception is encountered in self.multiplex():

    self.transcode()
        ├─ self._closepackets(self._iterators)
        │   └─ iterator.close() (for iterator in self._iterators)
        └─ self.excepthandler()
            ├─ self._excepthandler() (OVERRIDE this method in subclass)
            └─ notifyerror() (if notifyerror is provided)

    If an exception is encountered elsewhere:

    self.transcode()
        └─ self.excepthandler()
            ├─ self._excepthandler() (OVERRIDE this method in subclass)
            └─ notifyerror() (if notifyerror is provided)
    """
    from copy import deepcopy as copy
    trackclass = Track
    config = WeakRefProperty("config")

    def __init__(self, outputpath, tracks=[], targetsize=None, config=None):
        self.config = config
        self.outputpath = outputpath
        self.tracks = tracks
        self.targetsize = targetsize

        for track in tracks:
            track.container = self

        self._stop = threading.Event()
        self._unpaused = threading.Event()
        self._transcode_started = threading.Event()
        self.loadOverhead()
        self.newoverhead = {}
        self._transcodeThread = None
        self._files = set()

    @property
    def tracks(self):
        return self._tracks

    @tracks.setter
    def tracks(self, value):

        if not isinstance(value, TrackList):
            value = TrackList(value)

        value.container = self
        self._tracks = value

    @property
    def transcode_started(self):
        return self._transcode_started.isSet()

    def __reduce__(self):
        state = self.__getstate__()
        if state:
            return self.__class__, (self.outputpath,), state

        return self.__class__, (self.outputpath,)

    def __getstate__(self):
        d = OrderedDict()
        d["tracks"] = self.tracks
        d["targetsize"] = self.targetsize
        return d

    def __setstate__(self, state):
        self.targetsize = state.get("targetsize")
        self.tracks = state.get("tracks", [])

        for track in self.tracks:
            track.container = self

    @property
    def outputpathrel(self):
        """Input file path relative to config path."""
        if self.config:
            relpath = os.path.relpath(self.outputpath, self.config.workingdir)

            if relpath.startswith("../"):
                return self.outputpath

            else:
                return relpath

        return self.outputpath

    @outputpathrel.setter
    def outputpathrel(self, value):
        if self.config:
            self.outputpath = os.path.join(self.config.workingdir, value)

        else:
            self.outputpath = value

    @property
    def outputpathabs(self):
        """Input file absolute path."""
        return os.path.abspath(self.outputpath)

    @property
    def file_index(self):
        if self.config is not None and self in self.config.output_files:
            return self.config.output_files.index(self)

    def loadOverhead(self):
        try:
            overheadfile = open(
                f"{self.config.configstem}-{self.file_index}-overhead.json",
                "r")
            self.lastoverhead = json.JSONDecoder().decode(overheadfile.read())
            overheadfile.close()

        except Exception:
            self.lastoverhead = {}

        for k, track in enumerate(self.tracks):
            try:
                sizestatsfile = open(
                    f"{self.config.configstem}-{self.file_index}.{k}"
                    "-sizestats.dat", "rb")
                track.sizeStats = TrackStats.fromFile(sizestatsfile).data
                sizestatsfile.close()

            except Exception:
                track.sizeStats = None

    def saveOverhead(self):
        try:
            overheadfile = open(
                f"{self.config.configstem}-{self.file_index}"
                "-overhead.json", "w")
            print(json.JSONEncoder(indent=4).encode(
                self.lastoverhead), file=overheadfile)
            overheadfile.close()

        except Exception:
            pass

        for k, track in enumerate(self.tracks):
            try:
                stats = TrackStats(track.sizeStats)
                sizestatsfile = open(
                    f"{self.config.configstem}-{self.file_index}.{k}"
                    "-sizestats.dat", "wb")
                stats.toFile(sizestatsfile)
                sizestatsfile.close()

            except Exception:
                track.sizeStats = None

    def _checkpause(self, notifypaused=None):
        while True:
            self._unpaused.wait()

            if self._stop.isSet():
                break

            for path in self._files:
                try:
                    stat = os.statvfs(path)

                except FileNotFoundError:
                    continue

                if stat.f_bavail*stat.f_bsize < 64*1024**2:
                    if callable(notifypaused):
                        notifypaused("Transcode paused due to low disk space.")

                    self.pauseMux()
                    break

            else:
                return

    def _queuepacket(self, k, iterator, packets):
        if iterator is None:
            return

        if packets[k] is None:
            try:
                packet = next(iterator)

                if isinstance(packet, Exception):
                    raise packet

                packets[k] = packet

            except StopIteration:
                packets[k] = None

    def _queuepackets(self, iterators, packets):
        for k, iterator in enumerate(iterators):
            self._queuepacket(k, iterator, packets)

    def _iterPackets(self, *iterators):
        iterators = list(iterators)
        packets = [None]*len(iterators)

        while any([iterator is not None for iterator in iterators]):
            self._queuepackets(iterators, packets)

            ready_to_mux = [packet for packet in packets if packet is not None]

            if len(ready_to_mux) == 0:
                break

            packet = min(
                ready_to_mux, key=lambda packet: packet.pts*packet.time_base)
            k = packets.index(packet)
            packets[k] = None

            if packet is not None and len(packet.data):
                yield packet

        for packet in ready_to_mux:
            if packet is not None and len(packet.data):
                yield packet

    def _closepackets(self, iterators, logfile=None):
        print("--- Summary ---", file=logfile)
        for k, iterator in enumerate(iterators):
            try:
                iterator.close()

            except Exception:
                print(
                    "!!! EXCEPTION encountered while printing summary !!!",
                    file=logfile)
                cls, exc, tb = sys.exc_info()
                self._printexeption(exc, tb, logfile)

    def createTranscodeThread(self, pass_=0, encoderoverrides=[],
                              logfile=None, notifystats=None,
                              notifymux=None, notifypaused=None,
                              notifyfinish=None, notifycancelled=None,
                              notifyerror=None, notifyvencode=None,
                              autostart=True):
        return threading.Thread(
            target=self.transcode, args=(
                pass_, encoderoverrides, logfile, notifystats, notifymux,
                notifypaused, notifyfinish, notifycancelled, notifyerror,
                notifyvencode))

    def transcode(self, pass_=0, encoderoverrides=[], logfile=None,
                  notifystats=None, notifymux=None, notifypaused=None,
                  notifyfinish=None, notifycancelled=None, notifyerror=None,
                  notifyvencode=None):
        """
        Start transcode. If it is desired to run this method in a separate
        thread, self.createTranscodeThread() is provided.
        """
        self._unpaused.set()

        self._transcodeThread = threading.currentThread()

        try:
            try:
                if self._transcode_started.isSet():
                    raise RuntimeError("Muxer thread has already run.")

                strftime = time.strftime("%A, %B %-d, %Y, %-I:%M:%S %P %Z")
                print(f"*** Transcode started: {strftime} ***", file=logfile)
                print(
                    f"User/host: {os.getlogin()}@{socket.gethostname()}",
                    file=logfile)

                self._transcode_started.set()

                self.loadOverhead()

                if self.vtrack and callable(notifystats):
                    if isinstance(self.vtrack.sizeStats, numpy.ndarray):
                        notifystats(self.vtrack.sizeStats)

                self.open(logfile)
                self._iterators = iterators = self._prepare(
                    pass_, encoderoverrides, logfile, notifyvencode)

            except Exception:
                print("!!! EXCEPTION encountered during preparation !!!",
                      file=logfile)
                cls, exc, tb = sys.exc_info()
                self._printexeption(exc, tb, logfile)
                self.excepthandler(exc, tb, logfile, notifyerror)
                self._transcode_started.clear()
                self._stop.clear()
                raise

            try:
                self._multiplex(iterators, logfile, notifymux, notifypaused)

            except Exception:
                print("!!! EXCEPTION encountered during transcode !!!",
                      file=logfile)
                cls, exc, tb = sys.exc_info()
                self._printexeption(exc, tb, logfile)
                self._closepackets(iterators, logfile)
                self.excepthandler(exc, tb, logfile, notifyerror)
                self._transcode_started.clear()
                self._stop.clear()
                raise

            try:
                self._closepackets(iterators, logfile)
                self._wrapup(logfile, notifyfinish, notifycancelled)

            except Exception:
                print("!!! EXCEPTION encountered during wrap-up !!!",
                      file=logfile)
                cls, exc, tb = sys.exc_info()
                self._printexeption(exc, tb, logfile)
                self.excepthandler(exc, tb, logfile, notifyerror)
                raise

            finally:
                self._transcode_started.clear()
                self._stop.clear()

        finally:
            if logfile:
                logfile.flush()

            self._transcodeThread = None
            self._files.clear()

    def stopTranscode(self):
        self._unpaused.set()
        self._stop.set()

        if self._transcodeThread:
            self._transcodeThread.join()

        self._stop.clear()

    def _multiplex(self, iterators, logfile=None,
                   notifymux=None, notifypaused=None):
        for packet in self._iterPackets(*iterators):
            self._checkpause(notifypaused)

            if self._stop.isSet():
                return

            size = self._mux(packet)

            if callable(notifymux):
                notifymux(packet, size)

            track = self.tracks[packet.track_index]

            if track.codec in ("hevc", "libx265"):
                size -= 4

            track._sizes.append(size)

    def open(self, logfile=None):
        try:
            self._open()

        except Exception:
            print(f"FAILED to open {self.outputpathabs}", file=logfile)
            raise

        else:
            print(f"Output file: {self.outputpathabs}", file=logfile)

        self._files.add(self.outputpathabs)

    @abc.abstractmethod
    def _open(self):
        """Abstract method that opens/creates the container file."""
        raise NotImplementedError

    def _prepare(self, pass_=0, encoderoverrides=[],
                 logfile=None, notifyvencode=None):
        if self.targetsize is not None and pass_ != 1:
            print(f"Target file size: {h(self.targetsize)}", file=logfile)

        if pass_:
            print(f"Pass: {pass_:d}", file=logfile)

        if logfile is not None:
            logfile.flush()

        self._preparefile(logfile)
        return self._preparetracks(
            pass_, encoderoverrides, logfile, notifyvencode)

    @abc.abstractmethod
    def _preparefile(self, logfile=None):
        """
        Abstract method prepares container file, writing any header
        information except for track entries.
        """
        pass

    def _preparetracks(self, pass_, encoderoverrides=[],
                       logfile=None, notifyvencode=None):
        """
        Prepares packet iterators, and opens encoders.
        """
        print("--- Track Information ---", file=logfile)

        if (self.targetsize is not None
                and pass_ != 1
                and self.vtrack is not None):
            bitrate = self.bitrateFromTargetSize()
            self.newoverhead["targetSize"] = self.targetsize

            if self.newoverhead.get("bitrateAdj"):
                print(
                    "Applying bitrate adjustment: "
                    f"{self.newoverhead['bitrateAdj']:+,d} kbps",
                    file=logfile)

        else:
            bitrate = None

        iterators = []

        for k, (track,
                encoder_override) in enumerate(
                    zip_longest(self.tracks, encoderoverrides)):
            encoder_override = encoder_override or {}

            if track is self.vtrack:
                if notifyvencode is not None:
                    encoder_override.update(notifyencode=notifyvencode)

                if bitrate is not None:
                    encoder_override.update(bitrate=bitrate)

            if (track.encoder is not None
                    and track.codec in ("libx265", "libx264")
                    and pass_):
                stats = f"{self.config.configstem}-{self.file_index}"\
                    f".{track.track_index:d}-{track.encoder.codec}"\
                        "-multipass.log"
                self._files.add(stats)
                encoder_override.update(pass_=pass_, stats=stats)

                if pass_ == 1 and track.codec == "libx265":
                    encoder_override.update(crf=22)

            iterators.append(track._prepare(
                duration=self.duration, logfile=logfile, **encoder_override))

        if logfile:
            logfile.flush()

        return iterators

    @property
    def vtrack(self):
        for track in self.tracks:
            if track.type == "video" and track.encoder:
                return track

    @property
    def duration(self):
        if self.vtrack:
            return self.vtrack.duration + self.vtrack.delay

        elif len(self.tracks):
            duration = 0

            for track in self.tracks:
                if track.duration is None:
                    return 0

                duration = max(duration, track.duration + track.delay)

            return duration

        return 0

    @staticmethod
    def _printexeption(exc, tb, logfile):
        if logfile not in (sys.stdout, sys.stderr, None):
            print("".join(traceback.format_exception(
                type(exc), exc, tb)).rstrip("\n"), file=logfile)

    def excepthandler(self, exc, tb, logfile=None, notifyerror=None):
        self._transcode_started.clear()
        self._excepthandler(exc, tb, logfile)

        if callable(notifyerror):
            notifyerror(exc, tb)

        strftime = time.strftime("%A, %B %-d, %Y, %-I:%M:%S %P %Z")

        if type(exc) == KeyboardInterrupt:
            print(f"!!! Transcode interrupted: {strftime} !!!", file=logfile)

        else:
            print(f"!!! Transcode failed: {strftime} !!!", file=logfile)

    def _excepthandler(self, exc, tb, logfile=None):
        pass

    def _wrapup(self, logfile=None, notifyfinish=None, notifycancelled=None):
        self._transcode_started.clear()

        strftime = time.strftime("%A, %B %-d, %Y, %-I:%M:%S %P %Z")

        if self._stop.isSet():
            if callable(notifycancelled):
                notifycancelled()

            print(f"!!! Transcode cancelled: {strftime} !!!", file=logfile)

        else:
            self._finalize(logfile)
            self.lastoverhead, self.newoverhead = self.newoverhead, {}
            self.saveOverhead()

            if callable(notifyfinish):
                notifyfinish()

            print(f"*** Transcode completed: {strftime} ***", file=logfile)

    @abc.abstractmethod
    def _finalize(self, logfile=None):
        pass

    def calcOverhead(self):
        """
        Calculate expected overhead excluding overhead due to packets.

        I.e., overhead due to file headers, indexes, chapters, attachments, ...
        """
        return 0

    def minimumSize(self):
        overhead = self.calcOverhead()
        overheadbitrate = 0

        for track in self.tracks:
            overhead += track.calcOverhead()

            if (track is not self.vtrack
                    and track.encoder
                    and track.bitrate is not None):
                overheadbitrate += track.bitrate

        overheadbitrate += 16

        return overhead + 125*overheadbitrate*self.duration

    def bitrateFromTargetSize(self):
        overhead = self.calcOverhead()
        overheadbitrate = 0

        for track in self.tracks:
            overhead += track.calcOverhead()

            if (track is not self.vtrack
                    and track.encoder
                    and track.bitrate is not None):
                overheadbitrate += track.bitrate

        targetsize = self.targetsize - overhead

        try:
            bitrateAdj = int(self.lastoverhead.get("bitrateAdj", 0))

        except ValueError:
            bitrateAdj = 0

        if ("fileSize" in self.lastoverhead
                and "targetSize" in self.lastoverhead):
            try:
                diff = self.lastoverhead["targetSize"] - \
                    self.lastoverhead["fileSize"]

            except TypeError:
                diff = 0

            sizePerKbps = float(
                self.vtrack.framecount*self.vtrack.defaultDuration
                * self.vtrack.time_base*125)

            bitrateAdj += int(diff//sizePerKbps)

            self.newoverhead["bitrateAdj"] = bitrateAdj

        bitrate = targetsize/self.duration/125 - overheadbitrate
        return (bitrate/(self.vtrack.avgfps
                         * self.vtrack.defaultDuration*self.vtrack.time_base)
                + bitrateAdj)

    def pauseMux(self):
        self._unpaused.clear()

    def unpauseMux(self):
        self._unpaused.set()

    @property
    def dependencies(self):
        return set().union(*[track.dependencies for track in self.tracks])

    def validate(self):
        exceptions = []
        dir, file = os.path.split(self.outputpathabs)

        if (not os.path.isfile(self.outputpathabs)
                and not os.access(dir, os.W_OK)):
            exceptions.append(
                FileAccessDeniedError(
                    f"No write access to {self.outputpathrel}", self))

        if (os.path.isfile(self.outputpathabs)
                and not os.access(self.outputpath, os.W_OK)):
            exceptions.append(
                FileAccessDeniedError(
                    f"No write access to {self.outputpathrel}", self))

        exceptions.extend(exc
                          for track in self.tracks
                          for exc in track.validate())
        return exceptions

    def createTrack(self, source, encoder=None, filters=None, name=None,
                    language=None):
        return self.trackclass(source, encoder, filters, name=None,
                               language=None)

    def addTrack(self, source, encoder=None, filters=None, name=None,
                 language=None):
        track = self.createTrack(source, encoder, filters, name, language)
        self.tracks.append(track)
        return track

    def insertTrack(self, index, source, encoder=None, filters=None,
                    name=None, language=None):
        track = self.createTrack(source, encoder, filters, name, language)
        self.tracks.insert(index, track)
        return track

    @staticmethod
    def QtDlgClass():
        return

    def QtDlg(self, parent=None):
        dlgcls = self.QtDlgClass()

        if dlgcls is not None:
            dlg = dlgcls(parent)
            dlg.setOutputFile(self)
            return dlg
