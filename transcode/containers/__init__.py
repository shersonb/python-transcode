import os
import importlib

readers_by_ext = {}
readers = {}

writers_by_ext = {}
writers = {}


def scan():
    from transcode.containers.basereader import BaseReader
    from transcode.containers.basewriter import BaseWriter
    readers_by_ext.clear()
    readers.clear()
    writers_by_ext.clear()
    writers.clear()
    _path = os.path.split(__file__)[0]

    for _module in os.listdir(_path):
        if _module[0] in "_." or _module in ("basereader.py", "basewriter.py"):
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

            if isinstance(_cls, type) and issubclass(_cls, BaseReader) and\
                    _cls is not BaseReader:
                readers[f"{_cls.__module__}.{_cls.__name__}"] = _cls

                for ext in _cls.extensions:

                    if ext in readers_by_ext:
                        readers_by_ext[ext].append(_cls)

                    else:
                        readers_by_ext[ext] = [_cls]

            if isinstance(_cls, type) and issubclass(_cls, BaseWriter) and\
                    _cls is not BaseWriter:
                writers[f"{_cls.__module__}.{_cls.__name__}"] = _cls

                for ext in _cls.extensions:

                    if ext in writers_by_ext:
                        writers_by_ext[ext].append(_cls)

                    else:
                        writers_by_ext[ext] = [_cls]


scan()
