import os
import importlib
import  transcode.encoders.video.base

_path = os.path.split(__file__)[0]

for _module in os.listdir(_path):
    if _module[0] in "_." or _module == "base.py":
        continue

    if os.path.isfile(os.path.join(_path, _module)) and _module.lower().endswith(".py"):
        _module = importlib.import_module(f"{__name__}.{_module[:-3]}")

    elif os.path.isdir(os.path.join(_path, _module)) and os.path.isfile(os.path.join(_path, _module, "__init__.py")):
        _module = importlib.import_module(f"{__name__}.{_module}")

    else:
        continue

    del _module

del _path
