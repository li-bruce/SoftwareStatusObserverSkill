"""Keep each request on one build without serializing unrelated HTTP work.

The host owns session replacement and cleanup. Session methods own their state
locks; source parsing and socket I/O never hold the host's short registry lock.
"""

from contextlib import contextmanager
import threading


class SessionHost:
    def __init__(self, session, factory):
        self._current = session
        self._factory = factory
        self._lock = threading.RLock()
        self._reload_lock = threading.Lock()
        self._users = {}
        self._retired = set()
        self._closed = False

    @property
    def current(self):
        with self._lock:
            return self._current

    @contextmanager
    def borrow(self):
        """Pin one session until a request finishes, including its response write."""
        with self._lock:
            if self._closed:
                raise RuntimeError("Observer server is closed")
            session = self._current
            self._users[session] = self._users.get(session, 0) + 1
        try:
            yield session
        finally:
            close = False
            with self._lock:
                count = self._users[session] - 1
                if count:
                    self._users[session] = count
                else:
                    del self._users[session]
                    if session in self._retired:
                        self._retired.remove(session)
                        close = True
            if close:
                session.close()

    def reload(self):
        """Construct a replacement without blocking ingestion; publish it atomically."""
        with self._reload_lock, self.borrow() as previous:
            if previous.binding()["status"] == "current":
                return False
            replacement = self._factory(previous)
            replacement.program_url = previous.program_url
            replacement.data_status = previous.data_status
            with self._lock:
                closed = self._closed
                if not closed:
                    self._current = replacement
                    self._retired.add(previous)
            if closed:
                replacement.close()
                return False
            # The last request using the old build closes it. Old-build events
            # still undergo that session's source/build validation.
            return True

    def close(self):
        """Retire the current build; active requests release it on completion."""
        with self._lock:
            if self._closed:
                return
            self._closed = True
            current = self._current
            if self._users.get(current):
                self._retired.add(current)
                return
        current.close()
