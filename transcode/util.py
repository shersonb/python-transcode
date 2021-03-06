import collections
import numpy
from fractions import Fraction as QQ
import queue
import threading
import weakref
from copy import deepcopy


def search(array, value, dir="-"):
    """
    Searches a sorted (ascending) array for a value, or if value is not found,
    will attempt to find closest value.

    Specifying dir="-" finds index of greatest value in array less than
    or equal to the given value.

    Specifying dir="+" means find index of least value in array greater than
    or equal to the given value.

    Specifying dir="*" means find index of value closest to the given value.
    """

    if value < array[0]:
        if dir == "+":
            return 0

        else:
            raise IndexError(f"No value found before {value}.")

    if value > array[-1]:
        if dir == "-":
            return len(array) - 1

        else:
            raise IndexError(f"No value found after {value}.")

    J = 0
    K = len(array) - 1

    while True:
        if value == array[J]:
            return J

        elif value == array[K]:
            return K

        elif K == J + 1:
            if dir == "-":
                return J

            elif dir == "+":
                return K

            elif dir == "*":
                return min((J, K), key=lambda n: abs(n - value))

        N = (J + K)//2

        if value < array[N]:
            K = N

        elif value > array[N]:
            J = N

        elif value == array[N]:
            return N


def h(size):
    """Format 'size' (given in bytes) using KB, MB, GB, or TB as needed."""
    if abs(size) < 1024:
        return f"{size:,.0f} bytes"

    elif abs(size) < 1024**2:
        return f"{size/1024:,.2f} KB"

    elif abs(size) < 1024**3:
        return f"{size/1024**2:,.3f} MB"

    elif abs(size) < 1024**4:
        return f"{size/1024**3:,.3f} GB"

    else:
        """
        Seriously.... Who is going to encode a media file
        measuring in terabytes?
        """
        return f"{size/1024**4:,.3f} TB"


class Packet(object):
    def __init__(self, data, pts=None, duration=None, time_base=None,
                 track_index=None, keyframe=False, invisible=False,
                 discardable=False, referenceBlocks=None):
        self.data = data
        self.pts = pts
        self.duration = duration
        self.time_base = time_base
        self.track_index = track_index
        self.keyframe = keyframe
        self.discardable = discardable
        self.referenceBlocks = referenceBlocks

    @property
    def size(self):
        return len(self.data)

    def __repr__(self):
        return (f"Packet(pts={self.pts}, duration={self.duration}, "
                f"size={self.size}, keyframe={self.keyframe}, "
                f"track_index={self.track_index})")


class WeakRefProperty(object):
    def __init__(self, arg):
        if isinstance(arg, str):
            self.attrname = arg
            self._attrname = f"_{arg}"
            self.fget = None

        elif callable(arg):
            self.fget = arg
            self.attrname = arg.__name__
            self._attrname = f"_{arg.__name__}"

        self.fset = None

    def __get__(self, inst, cls):
        if inst is None:
            return self

        ref = getattr(inst, self._attrname)

        if isinstance(ref, weakref.ref):
            ref = ref()

        if callable(self.fget):
            ref = self.fget(inst, ref)

        return ref

    def __set__(self, inst, value):
        if callable(self.fset):
            value = self.fset(inst, value)

        try:
            setattr(inst, self._attrname, weakref.ref(value))

        except TypeError:
            setattr(inst, self._attrname, value)

    def setter(self, func):
        new = deepcopy(self)
        new.fset = func
        return new


class ChildList(collections.UserList):
    from copy import deepcopy as copy

    def __init__(self, items=[], parent=None):
        self.data = list(items)
        self.parent = parent

    parent = WeakRefProperty("parent")

    @parent.setter
    def parent(self, value):
        for item in self:
            item.parent = value

        return value

    def append(self, item):
        item.parent = self.parent
        super().append(item)

    def insert(self, index, item):
        item.parent = self.parent
        super().insert(index, item)

    def extend(self, items):
        k = len(self)
        super().extend(items)
        for item in self[k:]:
            item.parent = self.parent

    def __reduce__(self):
        state = self.__getstate__()

        if state:
            return self.__class__, (), state, iter(self)

        return self.__class__, (), None, iter(self)

    def __getstate__(self):
        return


class llist(collections.UserList):
    """Subclass of Python's 'list' with doubly-linked list behavior."""
    from copy import deepcopy as copy

    def __init__(self, items=[]):
        self.data = list(items)

        if len(items):
            items[0].prev = None
            items[0].parent = self
            items[-1].next = None

            for item1, item2 in zip(items[:-1], items[1:]):
                item1.next = item2
                item2.prev = item1
                item2.parent = self

    def __reduce__(self):
        state = self.__getstate__()

        if state:
            return self.__class__, (), state, iter(self)

        return self.__class__, (), None, iter(self)

    def __getstate__(self):
        return

    def append(self, item):
        if len(self):
            prev = self[-1]

        else:
            prev = None

        super().append(item)

        item.prev = prev
        item.parent = self

        if prev is not None:
            prev.next = item

    def extend(self, iterable):
        k = len(self)

        super().extend(iterable)

        if len(self):
            self[-1].next = None

        if k > 0:
            self[k].prev = self[k - 1]
            self[k - 1].next = self[k]

        elif len(self) > k:
            self[k].prev = None

        if len(self) > k:
            self[k].parent = self

        for item1, item2 in zip(self[k:-1], self[k+1:]):
            item1.next = item2
            item2.prev = item1
            item2.parent = self

    def insert(self, index, item):
        L = len(self)

        if index == 0 or index <= -L:
            prev = None

        else:
            prev = self[max(-L, index) - 1]

        if index >= L:
            next = None

        else:
            next = self[max(-L, index)]

        super().insert(index, item)

        if prev is not None:
            prev.next = item

        if next is not None:
            next.prev = item

        item.next = next
        item.prev = prev
        item.parent = self

    def __delitem__(self, index):
        item = self[index]
        prev = item.prev
        next = item.next
        item.next = item.prev = item.parent = None

        if (index % len(self)) > 0:
            prev.next = next

        if 0 <= (index % len(self)) < len(self) - 1:
            next.prev = prev

        super().__delitem__(index)

    def __setitem__(self, index, item):
        olditem = self[index]
        olditem.prev.next = item
        item.prev = olditem.prev
        olditem.next.prev = item
        item.next = olditem.next
        olditem.next = olditem.prev = olditem.parent = None
        item.parent = self
        super().__setitem__(index, item)

    def pop(self, index):
        item = self[index]

        if (index % len(self)) > 0:
            self[index - 1].next = item.next

        if 0 <= (index % len(self)) < len(self) - 1:
            self[index + 1].prev = item.prev

        item.next = item.prev = item.parent = None
        return super().pop(index)

    @property
    def start(self):
        if len(self):
            return self[0]

    @property
    def end(self):
        if len(self):
            return self[-1]


class cached(property):
    def __init__(self, fget=None, fset=None, fdel=None, doc=None):
        self._attrname = f"_{fget.__name__}"
        super().__init__(fget, fset, fdel, doc)

    def __get__(self, inst, cls):
        if inst is None:
            return self

        if (not hasattr(inst, self._attrname)
                or getattr(inst, self._attrname) is None):
            value = self.fget(inst)
            self.__set__(inst, value)

        return getattr(inst, self._attrname)

    def __delete__(self, inst):
        if (hasattr(inst, self._attrname)
                and getattr(inst, self._attrname) is None):
            return

        if callable(self.fdel):
            self.fdel(inst)

        self.__set__(inst, None)

    def __set__(self, inst, value):
        if callable(self.fset):
            self.fset(inst, value)

        setattr(inst, self._attrname, value)


def numpify(m, dtype=numpy.int0):
    if isinstance(m, (int, tuple, list, range, QQ)):
        return numpy.int0(m)

    elif isinstance(m, dtype):
        return m

    elif isinstance(m, numpy.ndarray) and m.dtype == dtype:
        return m

    raise TypeError("Cannot convert value into a numpy object with "
                    f"dtype={dtype.__name__}.")


def applyState(obj, state=None, items=None, dictitems=None, memo={}):
    if state is not None:
        obj.__setstate__(state)

    if items is not None or dictitems is not None:
        obj.clear()

    if items is not None:
        for item in items:
            obj.append(deepcopy(item, memo))

    if dictitems is not None:
        for key, value in dictitems:
            obj[deepcopy(key, memo)] = deepcopy(value, memo)


class WorkaheadIterator(object):
    def __init__(self, iterator, maxqueue=50):
        self._queue = queue.Queue(maxsize=maxqueue)
        self._iterator = iterator
        self._thread = threading.Thread(target=self._readIterator)
        self._thread.daemon = True
        self._lock = threading.Lock()
        self._stopped = False
        self._thread.start()

    def _readIterator(self):
        try:
            while True:
                with self._lock:
                    item = next(self._iterator)

                    if self._stopped:
                        break

                self._queue.put(item)

        except StopIteration:
            pass

        except BaseException as exc:
            self._queue.put(exc)
            raise

        self._queue.put(StopIteration())

    def __iter__(self):
        return self

    def __next__(self):
        with self._lock:
            if self._stopped:
                raise StopIteration()

        item = self._queue.get()

        if (isinstance(item, BaseException)
                or (isinstance(item, type)
                    and issubclass(item, BaseException))):
            with self._lock:
                self._stopped = True

            raise item

        return item

    def close(self):
        with self._lock:
            self._stopped = True
            self._iterator.close()

        try:
            self._queue.get(timeout=0)

        except queue.Empty:
            pass


class WeakRefList(collections.UserList):
    """Subclass of Python's 'list' storing only weak references."""

    def __init__(self, items=[]):
        self.data = list(map(self._toweakref, items))

    @staticmethod
    def _toweakref(obj):
        try:
            return weakref.ref(obj)

        except TypeError:
            return obj

    @staticmethod
    def _fromweakref(obj):
        if isinstance(obj, weakref.ref):
            return obj()

        return obj

    def __iter__(self):
        return map(self._fromweakref, self.data)

    def __reduce__(self):
        state = self.__getstate__()

        if state:
            return self.__class__, (), state, iter(self)

        return self.__class__, (), None, iter(self)

    def __getstate__(self):
        return

    def append(self, item):
        super().append(self._toweakref(item))

    def extend(self, iterable):
        super().extend(map(self._toweakref, iterable))

    def insert(self, index, item):
        super().insert(index, self._toweakref(item))

    def __setitem__(self, index, item):
        super().__setitem__(index, self._toweakref(item))

    def __getitem__(self, index):
        return self._fromweakref(super().__setitem__(index))

    def pop(self, index):
        return self._fromweakref(super().pop(index))

    def __contains__(self, item):
        for other in self:
            if item == other:
                return True

        return False

    def index(self, item):
        for k, other in enumerate(self):
            if item == other:
                return k

        raise ValueError(f"{item} not in list")

    def remove(self, item):
        for k, other in enumerate(self):
            if item == other:
                del self[k]
                return

        raise ValueError("WeakRefList.remove(x): x not in list")

    def clean(self):
        for ref in self.data.copy():
            if isinstance(ref, weakref.ref) and ref() is None:
                self.data.remove(ref)


class ValidationException(BaseException):
    def __init__(self, message, obj, prev=None):
        self.message = message
        self.obj = obj


class SourceError(ValidationException):
    pass


class BrokenReference(ValidationException):
    pass


class IncompatibleSource(ValidationException):
    pass


class FileMissingError(ValidationException):
    pass


class FileAccessDeniedError(ValidationException):
    pass


class EncoderError(ValidationException):
    pass
