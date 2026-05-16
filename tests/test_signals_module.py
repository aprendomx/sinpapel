"""A1 — Tests for the 4 custom domain Signals in sinpapel.signals.

These are loose-coupling Signal() declarations for sinpapel-webhooks v0.2.0+
consumers. They live alongside the existing cache-invalidation receivers.
"""
from __future__ import annotations

from django.dispatch import Signal


def test_signals_module_exposes_four_signals():
    """sinpapel.signals must expose the 4 custom domain Signal() instances."""
    from sinpapel import signals as signals_mod

    expected = (
        "predicate_failed",
        "sla_breached",
        "sla_action_executed",
        "transition_preview_requested",
    )
    for name in expected:
        assert hasattr(signals_mod, name), (
            f"sinpapel.signals must expose '{name}'"
        )
        sig = getattr(signals_mod, name)
        assert isinstance(sig, Signal), (
            f"sinpapel.signals.{name} must be a django.dispatch.Signal "
            f"instance, got {type(sig).__name__}"
        )


def test_signals_can_be_connected_and_send_robust_does_not_raise():
    """Signals must be connectable; send_robust must not propagate listener
    errors (default Django behavior) and must deliver kwargs to listeners."""
    from sinpapel import signals as signals_mod

    captured: list[dict] = []

    def _ok_listener(sender, **kwargs):
        captured.append({"sender": sender, **kwargs})

    def _broken_listener(sender, **kwargs):
        raise RuntimeError("intentional listener failure")

    sentinel = object()

    for name in (
        "predicate_failed",
        "sla_breached",
        "sla_action_executed",
        "transition_preview_requested",
    ):
        sig = getattr(signals_mod, name)
        sig.connect(_ok_listener, weak=False, dispatch_uid=f"ok-{name}")
        sig.connect(
            _broken_listener, weak=False, dispatch_uid=f"broken-{name}"
        )
        try:
            results = sig.send_robust(
                sender=sentinel, foo="bar", target=sentinel
            )
            # send_robust returns list of (receiver, response_or_exception)
            assert len(results) == 2
            # No exception should bubble up from send_robust
        finally:
            sig.disconnect(dispatch_uid=f"ok-{name}")
            sig.disconnect(dispatch_uid=f"broken-{name}")

    # Each of the 4 signals invoked the ok listener once
    assert len(captured) == 4
    for c in captured:
        assert c["sender"] is sentinel
        assert c["foo"] == "bar"
        assert c["target"] is sentinel
