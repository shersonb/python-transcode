import av
import os
from collections import OrderedDict
#from . import video
from .base import EncoderConfig
import importlib
#from . import audio

vencoders = OrderedDict()
aencoders = OrderedDict()
sencoders = OrderedDict()

for codec in sorted(av.codecs_available):
    try:
        c = av.codec.Codec(codec, "w")

    except:
        pass

    else:
        if c.type == "video":
            vencoders[codec] = c.long_name
        if c.type == "audio":
            aencoders[codec] = c.long_name
        if c.type == "subtitle":
            sencoders[codec] = c.long_name

def createConfigObj(codec):
    if codec in encoders:
        return encoders[codec]()

    return EncoderConfig(codec)

encoders = {}

def scan():
    _path = os.path.split(__file__)[0]
    encoders.clear()

    for _module in os.listdir(_path):
        if _module[0] in "_." or _module in ("base.py",):
            continue

        if os.path.isfile(os.path.join(_path, _module)) and _module.lower().endswith(".py"):
            _module = importlib.import_module(f"{__name__}.{_module[:-3]}")

        elif os.path.isdir(os.path.join(_path, _module)) and os.path.isfile(os.path.join(_path, _module, "__init__.py")):
            _module = importlib.import_module(f"{__name__}.{_module}")

        else:
            continue

        for _key in dir(_module):
            _cls = getattr(_module, _key)

            if isinstance(_cls, type) and issubclass(_cls, EncoderConfig) and\
                    _cls not in (EncoderConfig,) and hasattr(_cls, "codec"):
                        encoders[_cls.codec] = _cls

scan()
