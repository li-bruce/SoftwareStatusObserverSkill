"""Refresh configured metadata and replace the Web build without restarting the application."""

import threading
from .sync import synchronize
from .contract import write_if_changed


class DataWatch:
    """One observer worker; it reads schemas and never applies a database migration."""

    def __init__(self, server, *, interval=2):
        self.server = server
        self.interval = max(0.2, interval)
        self.stopped = threading.Event()
        self.thread = threading.Thread(target=self.run, name="bo-database-watch", daemon=True)

    def settings(self):
        """Publish connection settings for the project's native development launcher."""
        session = self.server.bo_session
        write_if_changed(
            session.root / ".stategraph/collector.json",
            {
                "endpoint": f"http://127.0.0.1:{self.server.server_port}",
                "token": self.server.bo_token,
                "build_id": session.manifest["build_id"],
            },
        )

    def tick(self):
        """Expose failed collection as stale evidence; replace only a validated projection."""
        session = self.server.bo_session
        report = synchronize(
            session.root, model_path=session.path.relative_to(session.root).as_posix()
        )
        if self.stopped.is_set():
            return report
        session.data_status = report
        write_if_changed(session.root / ".stategraph/database-maintenance.json", report)
        if report["configured"] and report["valid"]:
            self.server.bo_reload()
            self.settings()
        return report

    def run(self):
        while not self.stopped.is_set():
            try:
                self.tick()
            except (OSError, ValueError, KeyError, TypeError) as exc:
                self.server.bo_session.data_status = {"valid": False, "errors": [str(exc)]}
            self.stopped.wait(self.interval)

    def start(self):
        self.thread.start()

    def close(self):
        self.stopped.set()
        if self.thread.is_alive():
            self.thread.join(2)
