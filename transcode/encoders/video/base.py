import av
from collections import deque
from fractions import Fraction as QQ

class VideoEncoderContext(object):
    def __init__(self, codec, framesource, notifyencode=None, logfile=None, **kwargs):
        if isinstance(codec, av.Codec):
            if not codec.is_encoder:
                raise TypeError("Codec object is not an encoder.")

            self._encoder = codec.create()

        else:
            self._encoder = av.CodecContext.create(codec, "w")

        print(f"        {kwargs}", file=logfile)

        for key, value in kwargs.items():
            setattr(self._encoder, key, value)

        #self._encoder.time_base = QQ(1, 10**9)

        self._framesource = framesource
        self._packets = deque()
        self._logfile = logfile
        self._notifyencode = notifyencode
        self._isopen = False
        self._packetsEncoded = 0
        self._streamSize = 0
        self._noMoreFrames = False
        self._success = False

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
        #self.close()
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
            frame.pts = int(10**9*frame.pts*frame.time_base)
            frame.time_base = QQ(1, 10**9)

        except StopIteration:
            self._success = True
            return self.stop()

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
        self._packetsEncoded += 1
        self._streamSize += packet.size
        return packet

class VideoEncoderConfig(object):
    def __init__(self, codec, bitrate=None, **options):
        self.codec = codec
        self.bitrate = bitrate

        slots = self.optionslots
        slots2 = [slot.replace("-", "_") for slot in slots]
        self.options = {}

        for option, value in options.items():
            if option.replace("-", "_").rstrip("_") not in slots2:
                raise ValueError(f"Invalid option '{option}' for codec '{codec}'.")

            self.options[slots[slots2.index(option.replace("-", "_").rstrip("_"))]] = value

    def create(self, framesource,
                width, height, sample_aspect_ratio=1,
                rate=None, pix_fmt=None, time_base=None,
                bitrate=None,
                notifyencode=None, logfile=None, **override):

        override2 = {}

        for option, value in override.items():
            if option.replace("-", "_").rstrip("_") not in slots2:
                raise ValueError(f"Invalid option '{option}' for codec '{codec}'.")

            override2[slots[slots2.index(option.replace("-", "_").rstrip("_"))]] = value

        options = self.options.copy()
        options.update(override2)
        options = {key: val for (key, val) in options.items() if val is not None}
        return VideoEncoderContext(self.codec, framesource, notifyencode, logfile,
                                   width=width, height=height, sample_aspect_ratio=sample_aspect_ratio,
                                   rate=rate, pix_fmt=pix_fmt, time_base=time_base,
                                   bit_rate=int(bitrate*1000 if bitrate is not None else self.bitrate*1000),
                                   options=options)

    @property
    def optionslots(self):
        if self.descriptor:
            return {option.name for option in self.descriptor.options}

        return set()

    @property
    def descriptor(self):
        if not hasattr(self, "_descriptor"):
            try:
                codecobj = av.Codec(self.codec, "w")

            except:
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
