from __future__ import annotations

import pytest

from app.services.mq import (
    LoggingMQPublisher,
    MQPublishResult,
    build_publisher,
)


def test_logging_mq_publisher_returns_success() -> None:
    publisher = LoggingMQPublisher(channel="test-channel")
    result = publisher.publish({"key": "value"})

    assert result.success is True
    assert result.error is None
    assert result.metadata == {"channel": "test-channel"}


def test_build_publisher_returns_none_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.services.mq as mq_module

    monkeypatch.setattr(mq_module.settings, "downstream_mq_enabled", False)
    result = build_publisher()
    assert result is None


def test_build_publisher_falls_back_to_logging_when_no_broker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.services.mq as mq_module

    monkeypatch.setattr(mq_module.settings, "downstream_mq_enabled", True)
    monkeypatch.setattr(
        mq_module.settings, "downstream_mq_exchange", "test-exchange"
    )
    monkeypatch.setattr(
        mq_module.settings, "downstream_mq_routing_key", "test-routing"
    )
    monkeypatch.setattr(mq_module.settings, "downstream_mq_broker_url", None)

    result = build_publisher()
    assert isinstance(result, LoggingMQPublisher)
    assert result.channel == "test-exchange"


def test_mq_publish_result_dataclass() -> None:
    result = MQPublishResult(success=True)
    assert result.success is True
    assert result.error is None
    assert result.metadata is None

    result2 = MQPublishResult(
        success=False, error="timeout", metadata={"retries": 3}
    )
    assert result2.success is False
    assert result2.error == "timeout"
    assert result2.metadata == {"retries": 3}
