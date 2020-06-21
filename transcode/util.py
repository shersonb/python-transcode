import collections
import numpy
from fractions import Fraction as QQ

def search(array, value, dir="-"):
    """
    Searches a sorted (ascending) array for a value, or if value is not found, will attempt to find closest value.

    Specifying dir="-" finds index of greatest value in array less than  or equal to the given value.
    Specifying dir="+" means find index of least value in array greater than or equal to the given value.
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
        """Seriously.... Who is going to encode a media file measuring in terabytes?"""
        return f"{size/1024**4:,.3f} TB"

class Packet(object):
    def __init__(self, data, pts=None, duration=None, time_base=None, track_index=None,
                 keyframe=False, invisible=False, discardable=False, referenceBlocks=None):
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

class ChildList(collections.UserList):
    def __init__(self, items=[], parent=None):
        self.data = list(items)
        self.parent = parent

    @property
    def parent(self):
        return self._parent

    @parent.setter
    def parent(self, value):
        for item in self:
            item.parent = value

        self._parent = value

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

        else:
            self[k].prev = None

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

        if (index % len(self)) > 0:
            self[index - 1].next = item.next

        if 0 <= (index % len(self)) < len(self) - 1:
            self[index + 1].prev = item.prev

        item.next = item.prev = item.parent = None
        super().__delitem__(index)

    def __setitem__(self, index, item):
        olditem = self[index]
        olditem.prev.next = item
        item.prev = olditem.prev
        olditem.next.prev = item
        item.next = olditem.next
        olditem.next = olditem.prev = olditem.parent = None
        item.parent = self
        super().__setitem__(self, index, item)

    def pop(self, index):
        item = self[index]

        if (index % len(self)) > 0:
            self[index - 1].next = item.next

        if 0 <= (index % len(self)) < len(self) - 1:
            self[index + 1].prev = item.prev

        item.next = item.prev = item.parent = None
        return super().pop(self, index)

    @property
    def start(self):
        return self[0]

    @property
    def end(self):
        return self[-1]

class cached(property):
    def __init__(self, fget=None, fset=None, fdel=None, doc=None):
        self._attrname = f"_{fget.__name__}"
        super().__init__(fget, fset, fdel, doc)

    def __get__(self, inst, cls):
        if inst is None:
            return self

        if not hasattr(inst, self._attrname) or getattr(inst, self._attrname) is None:
            value = self.fget(inst)
            self.__set__(inst, value)

        return getattr(inst, self._attrname)

    def __delete__(self, inst):
        if hasattr(inst, self._attrname) and getattr(inst, self._attrname) is None:
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

    raise TypeError("Cannot convert value into a numpy object with dtype=%s." % dtype.__name__)

