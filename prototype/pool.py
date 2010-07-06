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

class ThreadPool(object):
    """
    The thread pool.
    """
    def __init__(self, num_threads=4, max_tasks=16, timeout=32,
                 init_local=None, stack_size=None):
        """
        Create a new thread pool.

        Exactly num_threads will be spawned on start(). At most
        max_tasks can be queued at a time before add() blocks;
        add() blocks for at most timeout seconds before raising
        an exception.

        You can pass a callable with one argument to init_local
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
        assert timeout >= 1
        # TODO: undocumented and probably a very bad idea
        assert stack_size is None or stack_size > 16*4096
        if stack_size is not None:
            T.stack_size(stack_size)
        self.__queue = Q.Queue(max_tasks)
        self.__timeout = timeout
        self.__running = False
        self.__workers = []
        self.__init_local = init_local
        for _ in range(num_threads):
            worker = T.Thread(target=self.__wait_for_work)
            worker.daemon = True
            self.__workers.append(worker)

    def __wait_for_work(self):
        """
        Threads grab tasks and run them here.
        """
        storage = T.local()
        if self.__init_local is not None:
            self.__init_local(storage)
        while True:
            call, args, kwargs = self.__queue.get()
            required_args, _, _, _ = I.getargspec(call)
            try:
                if '_tp_local' in required_args:
                    call(_tp_local=storage, *args, **kwargs)
                else:
                    call(*args, **kwargs)
            except Exception as exc:
                L.exception(
                    "exception %s during %s(%s,%s) ignored by thread pool",
                    exc, call, args, kwargs
                )

    def add(self, call, *args, **kwargs):
        """
        Add a task.

        Raises exception if we have not started yet but the
        queue is full; if we have started and the queue is
        full add() will block for a while before raising an
        exception (the idea being that all threads are stuck
        and therefore we better get out now).

        You can access thread-local storage in your callable
        by requiring the special argument "_tp_local":

        def task(some, arg, u, ment, _tp_local):
            _tp_local.connection.rollback()
            ...
            _tp_local.connection.commit()
        ...
        pool.add(task, some, arg, u, ment)
        """
        if not self.__running:
            assert not self.__queue.full()
        self.__queue.put((call, args, kwargs), True, self.__timeout)

    def start(self):
        """
        Start the thread pool.
        """
        for worker in self.__workers:
            worker.start()
        self.__running = True

def test():
    """Simple example and test case."""
    from random import uniform
    from time import sleep
    from signal import pause
    def init_local(local):
        """A silly local. :-D"""
        local.x = uniform(0, 1)
        local.y = 0
    def task(number, _tp_local):
        """A silly task. :-D"""
        L.info("task %s thread local.x %s", number, _tp_local.x)
        L.info("task %s started", number)
        sleep(uniform(1, 4))
        L.info("task %s finished", number)
        _tp_local.y += 1
        L.info("thread %s has finished %s tasks", _tp_local.x, _tp_local.y)

    pool = ThreadPool(init_local=init_local)
    pool.start()
    L.info("starting to add tasks to pool")
    for i in range(32):
        pool.add(task, i)
    L.info("all tasks added, press CTRL-C to exit")
    pause()

if __name__ == "__main__":
    L.basicConfig(level=L.DEBUG,
                  format="%(asctime)s - %(levelname)s - %(message)s")
    test()
