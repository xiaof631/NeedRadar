"""封装与下游消息队列的交互。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

try:  # pragma: no cover - Kombu 由 Celery 提供
    from kombu import Connection, Exchange, Producer
except Exception:  # pragma: no cover - fallback
    Connection = None  # type: ignore[assignment]
    Exchange = None  # type: ignore[assignment]
    Producer = None  # type: ignore[assignment]

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


@dataclass(slots=True)
class MQPublishResult:
    """MQ 推送的返回结果。"""

    success: bool
    error: str | None = None
    metadata: dict[str, Any] | None = None


class BaseMQPublisher:
    """MQ 发布接口。"""

    def publish(self, payload: dict[str, Any]) -> MQPublishResult:  # pragma: no cover - 接口
        raise NotImplementedError


class LoggingMQPublisher(BaseMQPublisher):
    """用于本地开发的日志 Publisher。"""

    def __init__(self, channel: str) -> None:
        self.channel = channel

    def publish(self, payload: dict[str, Any]) -> MQPublishResult:
        logger.info("mq.publish", channel=self.channel, payload=payload)
        return MQPublishResult(success=True, metadata={"channel": self.channel})


class KombuMQPublisher(BaseMQPublisher):
    """基于 Kombu 的 MQ Publisher。"""

    def __init__(self, url: str, exchange_name: str, routing_key: str) -> None:
        if Connection is None or Exchange is None or Producer is None:  # pragma: no cover
            raise RuntimeError("kombu is not available")
        self._url = url
        self._exchange_name = exchange_name
        self._routing_key = routing_key

    def publish(self, payload: dict[str, Any]) -> MQPublishResult:
        assert Connection is not None and Exchange is not None and Producer is not None
        try:
            with Connection(self._url) as connection:
                exchange = Exchange(self._exchange_name, type="fanout", durable=True)
                producer = Producer(connection)
                producer.publish(
                    payload,
                    exchange=exchange,
                    routing_key=self._routing_key,
                    serializer="json",
                    retry=True,
                    retry_policy={"max_retries": 3, "interval_start": 0, "interval_step": 2},
                )
        except Exception as exc:  # pragma: no cover - 网络异常
            logger.warning("mq.publish.failed", error=str(exc))
            return MQPublishResult(success=False, error=str(exc))
        return MQPublishResult(
            success=True,
            metadata={"exchange": self._exchange_name, "routing_key": self._routing_key},
        )


def build_publisher() -> BaseMQPublisher | None:
    """根据配置创建 Publisher。"""

    if not settings.downstream_mq_enabled:
        return None
    exchange = settings.downstream_mq_exchange
    routing_key = settings.downstream_mq_routing_key
    if not settings.downstream_mq_broker_url:
        logger.warning("mq.publisher.no-broker", exchange=exchange)
        return LoggingMQPublisher(exchange)
    try:
        return KombuMQPublisher(
            settings.downstream_mq_broker_url,
            exchange,
            routing_key,
        )
    except Exception:  # pragma: no cover - fallback 日志模式
        logger.warning("mq.publisher.fallback", exchange=exchange, routing_key=routing_key)
        return LoggingMQPublisher(exchange)
