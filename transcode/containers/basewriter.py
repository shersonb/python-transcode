import transcode.util
import av
import threading
import time
import os
import sys
import traceback
from transcode.encoders.video.base import VideoEncoderContext
from itertools import zip_longest
import json
import numpy
from collections import OrderedDict
import ebml.ndarray
#from transcode.encoders.audio.base import AudioEncoderContext

class TrackStats(ebml.ndarray.EBMLNDArray):
    ebmlID = b"\x19\x14\xdc\x87"

class Track(object):
    from copy import deepcopy as copy

    def __init__(self, source, encoder=None, filters=None, name=None, language=None, delay=0, container=None):
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
            return type(self), (self.source, self.encoder, self.filters), state

        return type(self), (self.source, self.encoder, self.filters)

    def __getstate__(self):
        state = OrderedDict()

        if self.name:
            state["name"] = self.name

        if self.language:
            state["language"] = self.language

        if self.delay:
            state["delay"] = self.delay

        return state

    def __setstate__(self, state):
        self.name = state.get("name")
        self.language = state.get("language")
        self.delay = state.get("delay", 0)

    @property
    def filters(self):
        return self._filters

    @filters.setter
    def filters(self, value):
        self._filters = value

        if value is not None:
            value.prev = self.source

    @property
    def source(self):
        return self._source

    @source.setter
    def source(self, value):
        self._source = value
        try:
            self._filters.prev = value

        except AttributeError:
            pass

    @property
    def time_base(self):
        return self.container.time_base

    @property
    def extradata(self):
        if self.encoderContext:
            return self.encoderContext.extradata

        return self.source.extradata

    def _iterPackets(self, packets, duration=None, logfile=None):
        self._sizes = []
        track_index = self.track_index
        exit = False

        try:
            try:
                for packet in packets:
                    packet.track_index = track_index

                    if duration is not None and packet.keyframe and packet.pts >= duration/self.time_base:
                        break

                    if self.codec in ("hevc", "libx265"):
                        size = packet.size - 4

                    else:
                        size = packet.size

                    self._sizes.append(size)
                    yield packet

            except GeneratorExit:
                exit = True

            except BaseException as exc:
                yield exc

            else:
                if isinstance(self.sizeStats, numpy.ndarray) and self.sizeStats.shape[1] == len(self._sizes):
                    self.sizeStats = numpy.concatenate((self.sizeStats, (self._sizes,)))

                else:
                    self.sizeStats = numpy.array((self._sizes,))

            if not exit:
                while True:
                    yield None

        finally:
            print(f"Track {self.track_index}: {len(self._sizes)} packets, {sum(self._sizes)} bytes", file=logfile)
            packets.close()

    def _handlePacket(self, packet):
        return packet

    def prepare(self, duration=None, logfile=None, **kwargs):
        if self.type == "video":
            print(f"Track {self.track_index}: Video, {self.width}x{self.height}, {1/self.defaultDuration/self.time_base} fps, {self.format}", file=logfile)

        elif self.type == "audio":
            print(f"Track {self.track_index}: Audio, {self.rate}Hz, {self.layout}, {self.format}", file=logfile)

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
                packets = self.openencoder(duration=duration, logfile=logfile, **kwargs)

            except:
                print("FAILED to open encoder.", file=logfile)
                raise

        else:
            packets = self.openpackets(duration=duration, logfile=logfile)

        self._prepare(packets=packets, logfile=logfile)

        if self.encoder:
            return self._iterPackets(packets, logfile=logfile)

        return self._iterPackets(packets, duration=duration, logfile=logfile)

    def _prepare(self, packets, logfile=None, **kwargs):
        pass

    @property
    def type(self):
        return self.source.type

    @property
    def width(self):
        if self.encoder and self.filters:
            return self.filters.width

        return self.source.width

    @property
    def height(self):
        if self.encoder and self.filters:
            return self.filters.height

        return self.source.height

    @property
    def rate(self):
        if self.encoder and self.filters:
            return self.filters.rate

        return self.source.rate

    @property
    def channels(self):
        if self.encoder and self.filters:
            return self.filters.channels

        return self.source.channels

    @property
    def layout(self):
        if self.encoder and self.filters:
            return self.filters.layout

        return self.source.layout

    @property
    def sar(self):
        if self.encoder and self.filters:
            return self.filters.sar

        return self.source.sar

    @property
    def dar(self):
        if self.encoder and self.filters:
            return self.filters.dar

        return self.source.dar

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
                return self.filters.defaultDuration*self.filters.time_base/self.time_base

        if self.source.defaultDuration is not None:
            return self.source.defaultDuration*self.source.time_base/self.time_base

    @property
    def duration(self):
        if self.encoder and self.filters:
            return self.filters.duration

        return self.source.duration

    @property
    def bitdepth(self):
        if self.encoder:
            if self.encoder.bitdepth is not None:
                return self.encoder.bitdepth

            elif self.filters and self.filters.bitdepth:
                return self.filters.bitdepth

        return self.source.bitdepth

    @property
    def format(self):
        if self.encoder:
            if self.encoder.format is not None:
                return self.encoder.format

            elif self.filters and self.filters.format:
                return self.filters.format

        return self.source.format

    @property
    def avgfps(self):
        return self.framecount/self.duration

    @property
    def track_index(self):
        if self.container is not None:
            return self.container.tracks.index(self)

    @property
    def codec(self):
        if self.encoder:
            return self.encoder.codec

        return self.source.codec

    def _iterFrames(self, duration=None, logfile=None):
        if self.filters:
            frames = self.filters.iterFrames(end=int(duration/self.filters.time_base), whence="pts")

        else:
            frames = self.source.iterFrames(end=int(duration/self.source.time_base), whence="pts")

        return frames

    def openencoder(self, duration=None, logfile=None, **kwargs):
        frames = self._iterFrames(duration, logfile)
        print(f"    Codec: {self.codec}", file=logfile)

        if self.type == "video":
            kwargs.update(width=self.width, height=self.height, sample_aspect_ratio=self.sar,
                          rate=1/self.defaultDuration/self.time_base)

        if self.format:
            kwargs.update(pix_fmt=self.format)

        if self.type == "audio":
            kwargs.update(rate=self.rate, channels=self.channels)

        packets = self.encoder.create(frames, logfile=logfile, time_base=self.time_base, **kwargs)
        packets.open()
        return packets

    def openpackets(self, duration=None, logfile=None):
        print(f"    Codec: {self.codec} (copy)", file=logfile)
        packets = self.source.iterPackets()
        return packets

    @property
    def framecount(self):
        return len(self.pts)
        #if self.encoder:
            #if self.type in ("video", "subtitle"):
                #if self.filters:
                    #return self.filters.framecount

                #return self.source.framecount

            #elif self.type == "audio":
                #return int(self.duration/self.defaultDuration) + bool(self.duration % self.defaultDuration > 0)

        #else:
            #return self.source.framecount

    @property
    def durations(self):
        if self.encoder and self.filters:
            return numpy.int0(self.filters.durations*float(self.filters.time_base/self.time_base))

        return numpy.int0(self.source.durations*float(self.source.time_base/self.time_base))

    @property
    def pts(self):
        if self.type == "audio":
            pts = numpy.arange(self.delay/self.time_base, min(self.duration, self.container.duration)/self.time_base, self.defaultDuration, dtype=numpy.int0)

        elif self.encoder and self.filters:
            pts = numpy.int0(self.filters.pts*float(self.filters.time_base/self.time_base))

        else:
            pts = numpy.int0(self.source.pts*float(self.source.time_base/self.time_base))

        try:
            n = transcode.util.search(pts, self.container.duration/self.time_base, dir="+")
            return pts[:n]

        except:
            return pts

    def frameIndexFromPts(self, pts, dir="+"):
        return transcode.util.search(self.pts, pts, dir)

class BaseWriter(object):
    from copy import deepcopy as copy
    trackclass = Track

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
            overheadfile = open(f"{self.config.configstem}-{self.file_index}-overhead.json", "r")
            self.lastoverhead = json.JSONDecoder().decode(overheadfile.read())
            overheadfile.close()

        except:
            self.lastoverhead = {}

        for k, track in enumerate(self.tracks):
            try:
                sizestatsfile = open(f"{self.config.configstem}-{self.file_index}.{k}-sizestats.dat", "rb")
                track.sizeStats = TrackStats.fromFile(sizestatsfile).data
                sizestatsfile.close()

            except:
                track.sizeStats = None

    def saveOverhead(self):
        try:
            overheadfile = open(f"{self.config.configstem}-{self.file_index}-overhead.json", "w")
            print(json.JSONEncoder(indent=4).encode(self.lastoverhead), file=overheadfile)
            overheadfile.close()

        except:
            pass

        for k, track in enumerate(self.tracks):
            try:
                stats = TrackStats(track.sizeStats)
                sizestatsfile = open(f"{self.config.configstem}-{self.file_index}.{k}-sizestats.dat", "wb")
                stats.toFile(sizestatsfile)
                sizestatsfile.close()

            except:
                track.sizeStats = None

    def _multiplex(self, *iterators):
        iterators = list(iterators)
        packets = [None]*len(iterators)

        while any([iterator is not None for iterator in iterators]):
            for k, iterator in enumerate(iterators):
                if iterator is None:
                    continue

                if packets[k] is None:
                    self._unpaused.wait()

                    if self._stop.isSet():
                        break

                    try:
                        packet = next(iterator)

                        if isinstance(packet, BaseException):
                            raise packet

                        packets[k] = packet

                    except StopIteration:
                        iterators[k] = None

            ready_to_mux = [packet for packet in packets if packet is not None]

            if len(ready_to_mux) == 0:
                break

            packet = min(ready_to_mux, key=lambda packet: packet.pts*packet.time_base)
            k = packets.index(packet)
            packets[k] = None
            yield packet

        for packet in ready_to_mux:
            if packet is not None:
                yield packet

    def createTranscodeThread(self, pass_=0, encoderoverrides=[], logfile=None, notifystats=None,
                notifymux=None, notifyfinish=None, notifyerror=None, notifyvencode=None, autostart=True):
        return threading.Thread(target=self.transcode, args=(pass_, encoderoverrides, logfile,
                                            notifystats, notifymux, notifyfinish, notifyerror, notifyvencode))

    def _closepackets(self, iterators, logfile=None):
        print(f"--- Summary ---", file=logfile)
        for k, iterator in enumerate(iterators):
            try:
                iterator.close()

            except:
                print("!!! EXCEPTION encountered while printing summary !!!", file=logfile)
                cls, exc, tb = sys.exc_info()
                self._printexeption(exc, tb, logfile)

    def stopTranscode(self):
        self._unpaused.set()
        self._stop.set()

        if self._transcodeThread:
            self._transcodeThread.join()

        self._stop.clear()

    def transcode(self, pass_=0, encoderoverrides=[], logfile=None, notifystats=None,
                  notifymux=None, notifyfinish=None, notifyerror=None, notifyvencode=None):
        self._unpaused.set()

        self._transcodeThread = threading.currentThread()

        try:
            try:
                if self._transcode_started.isSet():
                    raise RuntimeError("Muxer thread has already run.")

                strftime = time.strftime("%A, %B %-d, %Y, %-I:%M:%S %P %Z")
                print(f"*** Transcode started: {strftime} ***", file=logfile)

                self._transcode_started.set()

                self.loadOverhead()

                if self.vtrack and callable(notifystats):
                    if isinstance(self.vtrack.sizeStats, numpy.ndarray):
                        notifystats(self.vtrack.sizeStats)

                    #else:
                        #notifystats(numpy.zeros((0, ), dtype=numpy.int0))

                self.open(logfile)
                self._iterators = iterators = self.prepare(pass_, encoderoverrides, logfile, notifyvencode)

            except:
                print("!!! EXCEPTION encountered during preparation !!!", file=logfile)
                cls, exc, tb = sys.exc_info()
                self._printexeption(exc, tb, logfile)
                self.excepthandler(exc, tb, logfile, notifyerror)
                self._transcode_started.clear()
                self._stop.clear()
                raise

            try:
                self.multiplex(iterators, logfile, notifymux)

            except:
                print("!!! EXCEPTION encountered during transcode !!!", file=logfile)
                cls, exc, tb = sys.exc_info()
                self._printexeption(exc, tb, logfile)
                self._closepackets(iterators, logfile)
                self.excepthandler(exc, tb, logfile, notifyerror)
                self._transcode_started.clear()
                self._stop.clear()
                raise

            try:
                self._closepackets(iterators, logfile)
                self.wrapup(logfile, notifyfinish)

            except:
                print("!!! EXCEPTION encountered during wrap-up !!!", file=logfile)
                cls, exc, tb = sys.exc_info()
                self._printexeption(exc, tb, logfile)
                self.excepthandler(exc, tb, logfile, notifyerror)
                raise

            finally:
                self._transcode_started.clear()
                self._stop.clear()

            self.lastoverhead, self.newoverhead = self.newoverhead, {}
            self.saveOverhead()

        finally:
            if logfile:
                logfile.flush()

            self._transcodeThread = None

    def multiplex(self, iterators, logfile=None, notifymux=None):
        for packet in self._multiplex(*iterators):
            self._mux(packet)

            if callable(notifymux):
                notifymux(packet)

    def open(self, logfile=None):
        try:
            self._open()

        except:
            print(f"FAILED to open {self.outputpathabs}", file=logfile)
            raise

        else:
            print(f"Output file: {self.outputpathabs}", file=logfile)

    def _open(self):
        raise NotImplementedError

    def prepare(self, pass_=0, encoderoverrides=[], logfile=None, notifyvencode=None):
        if self.targetsize is not None and pass_ != 1:
            print(f"Target file size: {transcode.util.h(self.targetsize)}", file=logfile)

        if pass_:
            print(f"Pass: {pass_:d}", file=logfile)

        if logfile is not None:
            logfile.flush()

        self._prepare(logfile)
        return self._preparetracks(pass_, encoderoverrides, logfile, notifyvencode)

    def _prepare(self, logfile=None):
        pass

    def _preparetracks(self, pass_, encoderoverrides=[], logfile=None, notifyvencode=None):
        print("--- Track Information ---", file=logfile)

        vencoder_override = dict()

        if self.targetsize is not None and pass_ != 1 and self.vtrack is not None:
            bitrate = self.bitrateFromTargetSize()
            self.newoverhead["targetSize"] = self.targetsize

            if self.newoverhead.get("bitrateAdj"):
                print(f"Applying bitrate adjustment: {self.newoverhead['bitrateAdj']:+d} kbps", file=logfile)

            vencoder_override.update(bitrate=bitrate)

        if pass_ == 1:
            vencoder_override.update(crf=22)

        if pass_:
            stats = f"{self.config.configstem}-{self.file_index}.{self.vtrack.track_index:d}-{self.vtrack.encoder.codec}-multipass.log"
            vencoder_override.update(pass_=pass_, stats=stats)

        iterators = []

        for k, (track, encoder_override) in enumerate(zip_longest(self.tracks, encoderoverrides)):
            encoder_override = encoder_override or {}

            if track is self.vtrack:
                encoder_override.update(vencoder_override)
                iterators.append(track.prepare(duration=self.duration, notifyencode=notifyvencode, logfile=logfile, **encoder_override))

            else:
                iterators.append(track.prepare(duration=self.duration, logfile=logfile, **encoder_override))

        return iterators

    @property
    def vtrack(self):
        for track in self.tracks:
            if track.type == "video" and track.encoder:
                return track

    @property
    def duration(self):
        if self.vtrack:
            return self.vtrack.duration

        else:
            return max([track.duration for track in self.tracks])

    @staticmethod
    def _printexeption(exc, tb, logfile):
        if logfile not in (sys.stdout, sys.stderr, None):
            print("".join(traceback.format_exception(type(exc), exc, tb)).rstrip("\n"), file=logfile)

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

    def wrapup(self, logfile=None, notifyfinish=None):
        self._transcode_started.clear()
        self._wrapup(logfile)

        if callable(notifyfinish):
            notifyfinish()

        strftime = time.strftime("%A, %B %-d, %Y, %-I:%M:%S %P %Z")

        if self._stop.isSet():
            print(f"!!! Transcode cancelled: {strftime} !!!", file=logfile)

        else:
            print(f"*** Transcode completed: {strftime} ***", file=logfile)

    def _wrapup(self, logfile=None):
        pass

    def calcOverhead(self):
        """
        Calculate expected overhead excluding overhead due to packets.

        I.e., overhead due to file headers, indexes, chapters, attachments, ...
        """
        return 0

    def bitrateFromTargetSize(self):
        overhead = self.calcOverhead()
        overheadbitrate = 0

        for track in self.tracks:
            overhead += track.calcOverhead()

            if track is not self.vtrack and track.encoder and track.bitrate is not None:
                overheadbitrate += track.bitrate


        targetsize = self.targetsize - overhead

        try:
            bitrateAdj = int(self.lastoverhead.get("bitrateAdj", 0))

        except:
            bitrateAdj = 0

        if "fileSize" in self.lastoverhead and "targetSize" in self.lastoverhead:
            try:
                diff = self.lastoverhead["targetSize"] - self.lastoverhead["fileSize"]

            except:
                diff = 0

            sizePerKbps = float(self.vtrack.framecount*self.vtrack.defaultDuration*self.vtrack.time_base*125)

            bitrateAdj += int(diff//sizePerKbps)

            self.newoverhead["bitrateAdj"] = bitrateAdj

        bitrate = targetsize/self.duration/125 - overheadbitrate
        
        return bitrate/(self.vtrack.avgfps*self.vtrack.defaultDuration*self.vtrack.time_base) + bitrateAdj

