"""Live handle for one eval run: progress reporting and cooperative stopping.

The runner creates one per run and hands it to the executor, which reports
each finished case into it and polls ``stopping`` between cases. Stopping is
cooperative because the worker thread sits inside a blocking LLM call that
Python cannot interrupt: a stop takes effect at the next case boundary.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field


@dataclass
class RunControl:
    total: int = 0
    completed: int = 0
    _stop: threading.Event = field(
        default_factory=threading.Event, compare=False, repr=False
    )

    def set_total(self, total: int) -> None:
        self.total = total

    def case_finished(self) -> None:
        self.completed += 1

    def stop(self) -> None:
        self._stop.set()

    @property
    def stopping(self) -> bool:
        return self._stop.is_set()
