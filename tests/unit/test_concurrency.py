"""Unit tests for the process-local bounded concurrency guard (T066)."""

from albercik_chatbot.infra.concurrency import ChatConcurrencyGuard


def test_acquires_when_under_the_limit() -> None:
    guard = ChatConcurrencyGuard(limit=2)
    with guard.try_acquire() as acquired:
        assert acquired is True


def test_rejects_once_the_limit_is_held() -> None:
    guard = ChatConcurrencyGuard(limit=1)
    with guard.try_acquire() as first:
        assert first is True
        with guard.try_acquire() as second:
            assert second is False


def test_slot_is_released_after_the_context_exits() -> None:
    guard = ChatConcurrencyGuard(limit=1)
    with guard.try_acquire():
        pass

    with guard.try_acquire() as acquired:
        assert acquired is True


def test_slot_is_released_even_if_the_body_raises() -> None:
    guard = ChatConcurrencyGuard(limit=1)
    try:
        with guard.try_acquire():
            raise RuntimeError("boom")
    except RuntimeError:
        pass

    with guard.try_acquire() as acquired:
        assert acquired is True
