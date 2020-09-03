import threading
import time
import weakref
from collections import OrderedDict

"""
expire_time is the max expire_time for this lru cache i.e for 15 min
"""


def lru_cache(max_size=1024, expire_time=15 * 60, **kwargs):
    def wrapper(func):
        return LRUCachedFunction(func, LRUCacheDict(
            max_size=max_size, expire_time=expire_time, **kwargs))

    return wrapper


def lock_(func):
    """
    If the LRUCacheDict is concurrent, then we should lock in order to avoid
   conflicts with threading, or the ThreadTrigger.
    """

    def with_lock(self, *args, **kwargs):
        if self.is_concurrent:
            with self._rlock:
                return func(self, *args, **kwargs)
        else:
            return func(self, *args, **kwargs)

    return with_lock


class LRUCacheDict(object):
    """
        Dictionary like object for cache
        objective: keep check on size if full delete from oldest
                    - time delay

        If the thread_clear option is specified, a background thread will clean
        it up every thread_clear_min_check seconds.

        Otherwise all the operation will result in clean up according to LRU
    """

    def __init__(self, max_size=1024, expire_time=15 * 60, is_clear_thread=False, thread_clear_min_check=0,
                 is_concurrent=False):
        self.max_size = max_size
        self.expire_time = expire_time

        self.__values = {}
        self.__expire_time = OrderedDict()
        self.__access_time = OrderedDict()
        self.is_clear_thread = is_clear_thread
        self.is_concurrent = is_concurrent or is_clear_thread
        if self.is_concurrent:
            self._rlock = threading.RLock()
        if is_clear_thread:
            t = self.EmptyCacheThread(self)
            t.start()

    class EmptyCacheThread(threading.Thread):
        daemon = True

        def __init__(self, cache, duration=60):
            self.ref = weakref.ref(cache)  # creating a opaque image of the present cache
            self.duration = duration
            super(LRUCacheDict.EmptyCacheThread, self).__init__()

        def run(self):
            while self.ref():
                c = self.ref()
                if c:
                    next_expiring_item = c.cleanup()
                    if next_expiring_item is None:
                        time.sleep(self.duration)
                    else:
                        time.sleep(next_expiring_item + 1)
                c = None

    @lock_
    def size(self):
        return len(self.__values)

    @lock_
    def clear(self):
        """
        Clears the Dictionary
        :return:
        """
        self.__values.clear()
        self.__expire_time.clear()  # time it will expire
        self.__access_time.clear()  # time it was accessed

    def __contains__(self, key):
        return self.has_keys(key)

    @lock_
    def has_keys(self, key):
        return key in self.__values

    @lock_
    def __setitem__(self, key, val):
        t = int(time.time())
        self.__delitem__(key)
        self.__values[key] = val
        self.__access_time[key] = t
        self.__expire_time[key] = t + self.expire_time
        self.cleanup()

    @lock_
    def __getitem__(self, key):
        t = int(time.time())
        del self.__access_time[key]
        self.__access_time[key] = t
        self.cleanup()
        return self.__values[key]

    @lock_
    def __delitem__(self, key):
        if key in self.__values:
            del self.__values[key]
            del self.__expire_time[key]
            del self.__access_time[key]

    @lock_
    def cleanup(self):
        if self.expire_time is None:
            return None
        t = int(time.time())
        # Delete Expired
        next_expiring_item = None
        for i in self.__expire_time:
            if self.__expire_time[i] < t:
                self.__delitem__(i)
            else:
                next_expiring_item = self.__expire_time[i]
                break

        # If we have more than self.max_size items, delete the oldest
        while len(self.__values) > self.max_size:
            for k in self.__access_time:
                self.__delitem__(k)
                break
        if not (next_expiring_item is None):
            return next_expiring_item - t
        else:
            return None


class LRUCachedFunction(object):
    def __init__(self, function, cache=None):
        if cache:
            self.cache = cache
        else:
            self.cache = LRUCacheDict()
        self.function = function
        self.__name__ = self.function.__name__

    def __call__(self, *args, **kwargs):
        """
        Canonical representation of the object
        :param args:
        :param kwargs:
        :return:
        """
        key = repr(
            (args, kwargs)) + "#" + self.__name__
        try:
            return self.cache[key]
        except KeyError:
            value = self.function(*args, **kwargs)
            self.cache[key] = value
            return value
