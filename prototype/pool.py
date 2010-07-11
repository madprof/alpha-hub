# |ALPHA| Hub - an authorization server for alpha-ioq3
# See files README and COPYING for copyright and licensing details.

"""
A throwaway thread pool with thread-local storage.

Throwaway Tasks
===============

A throwaway task is one you'd *like* to get done, but it's
not a big deal if it doesn't actually get done.

Scary as it may be, throwaway tasks are quite common in the
wild. They usually compute for a while and then *end* with
*one* operation that permanently changes the state of the
world: think of committing to a database or sending a lone
network packet.

Tasks that iterate while modifying the world, or tasks that
need to apply more than one operation to change the world
consistently, are *not* throwaway. You have been warned.

This thread pool assumes that all tasks are throwaway. It
doesn't care if they finish and it certainly doesn't care
to tell anyone that a task is done. Also, while some pools
go to great lengths to cope with blocked threads, this one
assumes that your application is broken if no progress can
be made for a certain amount of time; see add() below.

Thread-local Storage
====================

Threads frequently require some local storage of their own,
for example it may be necessary for each thread to hold its
own database connection.

This thread pool automatically equips each worker with local
storage; see __init__() and add() below.
"""

import inspect as I
import logging as L
import Queue as Q
import threading as T

class _NullHandler(L.Handler):
    """Logging handler that does nothing."""
    def emit(self, _record):
        pass
L.getLogger("com.urbanban.threading.throwaway.pool").addHandler(_NullHandler())

class _Worker(T.Thread):
    """Worker thread, don't instantiate directly!"""

    def __init__(self, task_queue, init_local=None):
        """Initialize and start a new worker."""
        super(_Worker, self).__init__()
        assert isinstance(task_queue, Q.Queue)
        assert init_local is None or callable(init_local)
        self.__task_queue = task_queue
        self.__init_local = init_local
        self.daemon = True
        self.start()

    def run(self):
        """Worker thread main loop."""
        storage = self.__make_local()
        self.__run_forever(storage)

    def __make_local(self):
        """Create and initialize thread-local storage."""
        storage = T.local()
        if self.__init_local is not None:
            self.__init_local(storage)
        return storage

    def __run_forever(self, storage):
        """Grab the next task and run it."""
        while True:
            task = self.__task_queue.get()
            self.__run_task(task, storage)
            self.__task_queue.task_done()

    def __run_task(self, task, storage):
        """Run a single task."""
        func, args, kwargs = task
        required_args, _, _, _ = I.getargspec(func)
        try:
            if '_tp_local' in required_args:
                func(_tp_local=storage, *args, **kwargs)
            else:
                func(*args, **kwargs)
        except Exception as exc:
            L.exception(
                "exception %s during %s ignored by thread pool",
                exc, func
            )

class ThreadPool(object):
    """The thread pool."""

    def __init__(self, num_threads=4, max_tasks=16, timeout=32,
                 init_local=None, stack_size=None):
        """
        Initialize and start a new thread pool.

        Exactly num_threads will be spawned. At most max_tasks
        can be queued before add() blocks; add() blocks for at
        most timeout seconds before raising an exception.

        You can pass a callable with one argument as init_local
        to initialize thread-local storage for each thread; see
        add() below for how to access thread-local storage from
        your tasks. For example:

            import sqlite3
            ...
            def init_local(local):
                local.connection = sqlite3.connect("some.db")
            ...
            pool = ThreadPool(init_local=init_local)
        """
        assert num_threads > 0
        assert max_tasks > 0
        assert timeout > 0
        # TODO: undocumented and probably a very bad idea
        assert stack_size is None or stack_size > 16*4096
        if stack_size is not None:
            T.stack_size(stack_size)
        self.__queue = Q.Queue(max_tasks)
        self.__timeout = timeout
        for _ in range(num_threads):
            _Worker(self.__queue, init_local)

    def add(self, func, *args, **kwargs):
        """
        Add a task.

        A task consists of a callable func and arguments for
        func. For example:

            def task(some, argu, ments=None):
                ...
            pool.add(task, act, ual, ments=parameters)

        You can access thread-local storage by requiring the
        special "_tp_local" argument for func. For example:

            def task(_tp_local, some, argu, ments=None):
                _tp_local.connection.rollback()
                ...
                _tp_local.connection.commit()
            ...
            pool.add(task, act, ual, ments=parameters)
        """
        assert callable(func)
        self.__queue.put((func, args, kwargs), True, self.__timeout)

def test():
    """Simple example and test case."""
    from random import uniform
    from time import sleep
    from signal import pause
    def init_local(local):
        """A silly local. :-D"""
        local.x = uniform(0, 1)
        local.y = 0
        L.info("init_local local.x %s", local.x)
    def task(number, _tp_local):
        """A silly task. :-D"""
        L.info("task %s thread local.x %s", number, _tp_local.x)
        L.info("task %s started", number)
        sleep(uniform(1, 4))
        L.info("task %s finished", number)
        _tp_local.y += 1
        L.info("thread %s has finished %s tasks", _tp_local.x, _tp_local.y)

    pool = ThreadPool(init_local=init_local)
    L.info("starting to add tasks to pool")
    for i in range(32):
        pool.add(task, i)
    L.info("all tasks added, press CTRL-C to exit")
    pause()

if __name__ == "__main__":
    L.basicConfig(level=L.DEBUG,
                  format="%(asctime)s - %(levelname)s - %(message)s")
    test()
