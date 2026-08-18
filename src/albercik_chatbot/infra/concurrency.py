"""Process-local bounded concurrency guard for paid LLM calls (tasks.md
T066).

A `threading.Semaphore`, not an `asyncio.Semaphore`: FastAPI runs a *sync*
`def post_chat(...)` route in a real OS thread via anyio's threadpool, so
concurrent requests genuinely execute in parallel across threads, not
cooperatively on one event loop — an `asyncio.Semaphore` would not see
them as concurrent at all and would not bound anything.

`try_acquire()` is non-blocking (`acquire(blocking=False)`): a request
that cannot get a slot fails fast (`ask_question.py` maps this to the
`unavailable` outcome) instead of queuing indefinitely behind an unbounded
wait, which would itself become a way to hang public requests.

Explicitly process-local: this correctly bounds concurrency within one
running `app` process/container (this deployment's docker-compose.yml
runs exactly one), but does NOT coordinate across multiple instances of
this service behind a load balancer. A future multi-instance deployment
would need this replaced with a cross-instance bound — e.g. a
Postgres-backed counter mirroring infra/rate_limit.py's atomic
`INSERT ... ON CONFLICT` approach — not this in-process primitive.
"""

import threading
from collections.abc import Iterator
from contextlib import contextmanager


class ChatConcurrencyGuard:
    def __init__(self, limit: int) -> None:
        self._semaphore = threading.Semaphore(limit)

    @contextmanager
    def try_acquire(self) -> Iterator[bool]:
        acquired = self._semaphore.acquire(blocking=False)
        try:
            yield acquired
        finally:
            if acquired:
                self._semaphore.release()
