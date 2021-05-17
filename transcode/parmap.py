import ciqueue
import threading
import psutil

class ThreadPool(object):
    def __init__(self, nthreads=psutil.cpu_count(), qcls=ciqueue.Queue, qmaxsize=4):
        self._threadPool = []
        self._inputQueue = qcls(qmaxsize)

        for k in range(nthreads):
            T = threading.Thread(target=self._run, name="WorkerThread-%d" % k)
            T.daemon = True
            T.start()
            self._threadPool.append(T)

    def _run(self):
        while True:
            try:
                f, x, q = self._inputQueue.get()

            except ciqueue.Closed:
                break

            try:
                y = f(*x)

            except Exception as exc:
                q.put((f, x, None, exc))

            try:
                q.put((f, x, y, None))

            except (ciqueue.Closed, ciqueue.Interrupted):
                pass

    def submit(self, f, x, q):
        self._inputQueue.put((f, x, q))

    @property
    def threadCount(self):
        return len(self._threadPool)


mainpool = ThreadPool()


class map(object):
    def __init__(self, f, *iterables, threadpool=mainpool):
        self.f = f
        self.iterables = iterables
        self._threadPool = threadpool
        self._queueOfQueues = ciqueue.Queue()
        self._isdead = False

        for k in range(self._threadPool.threadCount + 2):
            self._queueOfQueues.put(ciqueue.Queue())

        self._resultsQueue = ciqueue.Queue()

        self._populateThread = threading.Thread(target=self._populateQueues)
        self._populateThread.daemon = True
        self._populateThread.start()

    def _populateQueues(self):
        try:
            for x in zip(*self.iterables):
                try:
                    q = self._queueOfQueues.get()

                except ciqueue.Closed:
                    return

                self._threadPool.submit(self.f, x, q)

                try:
                    self._resultsQueue.put(q)

                except ciqueue.Closed:
                    return

        finally:
            self._resultsQueue.close()

    def stop(self):
        self._isdead = True
        self._resultsQueue.interrupt()
        self._queueOfQueues.interrupt()

    def __iter__(self):
        while True:
            yield next(self)

    def __next__(self):
        if self._isdead:
            raise StopIteration

        try:
            q = self._resultsQueue.get()

        except ciqueue.Closed:
            self.stop()
            raise StopIteration

        try:
            f, x, y, exc = q.get()

        except ciqueue.Closed:
            self.stop()
            raise StopIteration

        if exc is not None:
            self.stop()
            raise exc

        self._queueOfQueues.put(q)
        return y
