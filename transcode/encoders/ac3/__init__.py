from ..base import EncoderContext
from ..base import EncoderConfig

class ac3Config(EncoderConfig):
    format = "fltp"
    codec = "ac3"

    def __init__(self, bitrate=None, **options):
        super().__init__("ac3", bitrate, **options)

    def create(self, framesource, rate=None, time_base=None,
                notifyencode=None, logfile=None, **override):
        if "format" in override:
            del override["format"]

        return super().create(framesource, rate=rate, format=self.format, time_base=time_base,
                              notifyencode=notifyencode, logfile=logfile, **override)

    def __reduce__(self):
        return type(self), (), self.__getstate__()
