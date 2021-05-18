import os
import importlib

_path = os.path.split(__file__)[0]

filters = {}


def scan():
    filters.clear()
    from .base import BaseAudioFilter

    for _module in os.listdir(_path):
        if _module[0] in "_." or _module in ("base.py",):
            continue

        if (os.path.isfile(os.path.join(_path, _module))
                and _module.lower().endswith(".py")):
            _module = importlib.import_module(f"{__name__}.{_module[:-3]}")

        elif (os.path.isdir(os.path.join(_path, _module))
              and os.path.isfile(os.path.join(_path, _module, "__init__.py"))):
            _module = importlib.import_module(f"{__name__}.{_module}")

        else:
            continue

        for _key in dir(_module):
            _cls = getattr(_module, _key)

            if (isinstance(_cls, type)
                    and issubclass(_cls, BaseAudioFilter)
                    and _cls is not BaseAudioFilter):
                filters[f"{_cls.__module__}.{_cls.__name__}"] = _cls


scan()
