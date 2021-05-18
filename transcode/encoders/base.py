import av
from collections import deque, OrderedDict
from fractions import Fraction as QQ
from ..util import Packet
from ..avarrays import aconvert


class EncoderContext(object):
    def __init__(self, codec, framesource, notifyencode=None,
                 logfile=None, **kwargs):
        if isinstance(codec, av.Codec):
            if not codec.is_encoder:
                raise TypeError("Codec object is not an encoder.")

            self._encoder = codec.create()

        else:
            self._encoder = av.CodecContext.create(codec, "w")

        for key, value in kwargs.items():
            if value is not None:
                setattr(self._encoder, key, value)

        if "time_base" not in kwargs:
            self._encoder.time_base = QQ(1, 10**9)

        self._framesource = framesource
        self._packets = deque()
        self._logfile = logfile
        self._notifyencode = notifyencode
        self._isopen = False
        self._packetsEncoded = 0
        self._streamSize = 0
        self._noMoreFrames = False
        self._success = False
        self._pts = 0

    @property
    def extradata(self):
        return self._encoder.extradata

    def open(self):
        self._encoder.open()
        self._isopen = True

        while len(self._packets) == 0:
            self._sendframe()

    def stop(self):
        packets = self._encoder.encode()
        self._packets.extend(packets)
        self._noMoreFrames = True
        self._encoder.close()
        return len(packets)

    def close(self):
        if not self._noMoreFrames:
            self._encoder.close()

        self._isopen = False

    def _sendframe(self):
        if self._noMoreFrames:
            raise StopIteration

        try:
            frame = next(self._framesource)
        except StopIteration:
            self._success = True
            return self.stop()

        if isinstance(frame, av.AudioFrame):
            frame = aconvert(frame, self._encoder.format.name)
            frame.pts = None

        else:
            frame.pts = int(10**9*frame.pts*frame.time_base)

        frame.time_base = QQ(1, 10**9)

        if callable(self._notifyencode):
            self._notifyencode(frame)

        packets = self._encoder.encode(frame)
        self._packets.extend(packets)

        if frame is None:
            self.close()

        return len(packets)

    def __next__(self):
        if not self._isopen and not self._noMoreFrames:
            self.open()

        while len(self._packets) == 0:
            self._sendframe()

        packet = self._packets.popleft()

        if packet.pts is None or self._encoder.type == "audio":
            packet = Packet(
                data=packet.to_bytes(), pts=self._pts,
                duration=packet.duration, keyframe=packet.is_keyframe,
                time_base=packet.time_base)

        else:
            packet = Packet(
                data=packet.to_bytes(), pts=packet.pts,
                duration=packet.duration, keyframe=packet.is_keyframe,
                time_base=packet.time_base)

        self._pts = packet.pts + packet.duration
        self._packetsEncoded += 1
        self._streamSize += packet.size
        return packet

    def __iter__(self):
        return self


class EncoderConfig(object):
    format = None
    from copy import deepcopy as copy

    @property
    def bitdepth(self):
        if format in ("s16", "s16p"):
            return 16

        if format in ("s32", "s32p"):
            return 32

    def __init__(self, codec, bitrate=None, **options):
        self.codec = codec
        self.bitrate = bitrate

        slots = list(self.optionslots)
        slots2 = [slot.replace("-", "_") for slot in slots]
        self.options = {}

        for option, value in options.items():
            if option.replace("-", "_").rstrip("_") not in slots2:
                raise ValueError(
                    f"Invalid option '{option}' for codec '{codec}'.")

            self.options[slots[slots2.index(
                option.replace("-", "_").rstrip("_"))]] = value

    def create(self, framesource,
               width=None, height=None, sample_aspect_ratio=None,
               rate=None, pix_fmt=None, format=None, time_base=None,
               bitrate=None, channels=None, layout=None,
               notifyencode=None, logfile=None, **override):

        slots = list(self.optionslots)
        slots2 = [slot.replace("-", "_") for slot in slots]
        override2 = {}

        for option, value in override.items():
            if option.replace("-", "_").rstrip("_") not in slots2:
                raise ValueError(
                    f"Invalid option '{option}' for codec '{self.codec}'.")

            override2[slots[slots2.index(
                option.replace("-", "_").rstrip("_"))]] = value

        options = self.options.copy()
        options.update(override2)
        options = {key: val for (
            key, val) in options.items() if val is not None}
        return EncoderContext(
            self.codec, framesource, notifyencode, logfile, width=width,
            height=height, sample_aspect_ratio=sample_aspect_ratio, rate=rate,
            pix_fmt=pix_fmt, format=format, time_base=time_base,
            channels=channels, layout=layout,
            bit_rate=int(
                bitrate*1000
                if bitrate is not None
                else self.bitrate*1000),
            options=options)

    @property
    def optionslots(self):
        if self.avoptions:
            return {option.name for option in self.avoptions}

        return set()

    @property
    def descriptor(self):
        if not hasattr(self, "_descriptor"):
            try:
                codecobj = av.Codec(self.codec, "w")

            except Exception:
                return

            self._descriptor = codecobj.descriptor

        return self._descriptor

    @property
    def type(self):
        if self.descriptor:
            return self.descriptor.type

    @property
    def avoptions(self):
        if self.descriptor:
            return self.descriptor.options

    def __reduce__(self):
        return type(self), (self.codec,), self.__getstate__()

    def __getstate__(self):
        state = OrderedDict()

        if self.bitrate:
            state["bitrate"] = self.bitrate

        state.update(self.options)
        return state

    def __setstate__(self, state):
        if "bitrate" in state:
            self.bitrate = state.pop("bitrate")

        options = self.options
        options.clear()

        for option in self.optionslots:
            if option in state:
                options[option] = state[option]

    def __dir__(self):
        dir = super().__dir__()

        if self.avoptions:
            for option in self.avoptions:
                attrname = option.name.replace("-", "_")

                if attrname == "pass":
                    attrname = "pass_"

                if attrname not in dir:
                    dir.append(attrname)

        dir.sort()
        return dir

    def __getattribute__(self, attr):
        if (attr in ("options", "copy", "codec", "avoptions", "descriptor",
                     "type", "optionslots", "create")
                or attr.startswith("_")):
            return super().__getattribute__(attr)

        if self.avoptions:
            optname = attr.rstrip("_")

            for option in self.avoptions:
                if optname.replace("-", "_") == option.name.replace("-", "_"):
                    return self.options.get(option.name)

        return super().__getattribute__(attr)

    def __delattr__(self, attr):
        if (attr in ("options", "codec", "avoptions", "descriptor", "type",
                     "optionslots", "create")
                or attr.startswith("_")):
            return super().__delattr__(attr)

        if self.avoptions:
            optname = attr.rstrip("_")

            for option in self.avoptions:
                if (optname == option.name.replace("-", "_")
                        and option.name in self.options):
                    del self.options[option.name]

        return super().__delattr__(attr)

    def __setattr__(self, attr, value):
        if (attr in ("options", "codec", "avoptions", "descriptor", "type",
                     "optionslots", "create")
                or attr.startswith("_")):
            return super().__setattr__(attr, value)

        if self.avoptions:
            optname = attr.rstrip("_")

            for option in self.avoptions:
                if optname.replace("-", "_") == option.name.replace("-", "_"):
                    if value is None:
                        if option.name in self.options:
                            del self.options[option.name]

                        return

                    else:
                        if option.type == "FLOAT":
                            value = float(value)

                        elif option.type == "INT":
                            value = int(value)

                        elif option.type == "STRING":
                            value = str(value)

                        elif option.type == "BOOL":
                            value = bool(value)

                        self.options[option.name] = value
                        return

        return super().__setattr__(attr, value)

    @property
    def QtDlgClass(self):
        if self.avoptions:
            from transcode.pyqtgui.qencoderconfig import QEncoderConfigDlg
            return QEncoderConfigDlg

    def QtDlg(self, parent=None):
        if self.QtDlgClass is not None:
            return self.QtDlgClass(self, parent)
