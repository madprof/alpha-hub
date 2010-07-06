# |ALPHA| Hub - an authorization server for alpha-ioq3
# See files README and COPYING for copyright and licensing details.

"""
A throwaway thread pool.

A throwaway task is one you'd *like* to get done, but it's
not a big deal if it doesn't actually get done.

Scary as it may be, throwaway tasks are quite common in the
wild. They usually compute for a while and then *end* with
*one* operation that permanently changes the state of the
system: think if committing a transaction to a database or
sending a lone network packet.

Tasks that iterate while modifying the system's state, or
tasks that need to apply more than one operation to change
the state consistently, are *not* throwaway. You have been
warned.

This thread pool takes advantage of the throwaway nature of
tasks by simply not caring if they finish. It also doesn't
try to do anything fancy about tasks that never terminate.
Together, these anti-constraints make for simple code.

p = ThreadPool(num_threads=10, max_tasks=20)
p.start()
p.add(somecallable, some, parameters, for, the="callable")
...
"""

import logging
from Queue import Queue
from threading import Thread, stack_size

class ThreadPool(object):
    """
    The thread pool.
    """
    def __init__(self, num_threads=4, max_tasks=16, timeout=32,
                 _stack_size=None):
        """
        Create a new thread pool.

        Exactly num_threads will be spawned on start(). At most
        max_tasks can be queued at a time before add() blocks;
        add() blocks for at most timeout seconds before raising
        an exception.
        """
        assert num_threads > 0
        assert max_tasks > 0
        assert timeout > 1
        # TODO: undocumented and probably a very bad idea
        assert _stack_size is None or _stack_size > 16*4096
        if _stack_size is not None:
            stack_size(_stack_size)
        self.__queue = Queue(max_tasks)
        self.__timeout = timeout
        self.__running = False
        self.__workers = []
        for _ in range(num_threads):
            thread = Thread(target=self.__wait_for_work)
            thread.daemon = True
            self.__workers.append(thread)

    def __wait_for_work(self):
        """
        Threads grab tasks and run them here.
        """
        while True:
            call, args, kwargs = self.__queue.get()
            try:
                call(*args, **kwargs)
            except Exception as exc:
                logging.exception(
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
    def task(number):
        """A silly task. :-D"""
        logging.info("task %s started", number)
        sleep(uniform(1, 4))
        logging.info("task %s finished", number)

    pool = ThreadPool()
    pool.start()
    logging.info("starting to add tasks to pool")
    for i in range(32):
        pool.add(task, i)
    logging.info("all tasks added, press CTRL-C to exit")
    pause()

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG,
                        format="%(asctime)s - %(levelname)s - %(message)s")
    test()
