"""关键词搜索量数据源封装。"""

from __future__ import annotations

import asyncio
import re
from collections.abc import Sequence
from dataclasses import dataclass

import httpx

from app.core.config import get_settings

# 用于判断短语是否包含中日韩字符，决定 suggest 请求的语言参数。
_CJK_RE = re.compile(r"[\u4e00-\u9fff]")


class KeywordProviderError(Exception):
    """关键词数据源请求失败。"""


class KeywordRateLimitedError(KeywordProviderError):
    """数据源限流，携带已完成部分的结果。"""

    def __init__(self, message: str, *, partial: dict[str, KeywordMetrics]) -> None:
        super().__init__(message)
        self.partial = partial


@dataclass(slots=True)
class KeywordMetrics:
    """单个关键词的搜索指标；免费存在性校验时只有 search_volume 为 None 的确认标记。"""

    search_volume: int | None = None
    keyword_difficulty: int | None = None
    cpc: float | None = None
    competition: str | None = None


class KeywordDataProvider:
    """按短语批量查询搜索指标的接口约定。"""

    async def fetch_metrics(self, phrases: Sequence[str]) -> dict[str, KeywordMetrics]:
        raise NotImplementedError


class DataForSEOProvider(KeywordDataProvider):
    """DataForSEO Labs Google 关键词搜索量接口。"""

    def __init__(
        self,
        *,
        login: str,
        password: str,
        sandbox: bool = False,
        timeout: float = 30.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._login = login
        self._password = password
        self._timeout = timeout
        self._client = client
        self._base_url = (
            "https://sandbox.dataforseo.com" if sandbox else "https://api.dataforseo.com"
        )

    async def fetch_metrics(self, phrases: Sequence[str]) -> dict[str, KeywordMetrics]:
        if not phrases:
            return {}
        payload = [
            {
                "keywords": list(phrases),
                "location_code": 2840,
                "language_code": "en",
            }
        ]
        close_client = False
        client = self._client
        if client is None:
            client = httpx.AsyncClient(timeout=self._timeout)
            close_client = True
        try:
            response = await client.post(
                f"{self._base_url}/v3/dataforseo_labs/google/keyword_search_volume/live",
                json=payload,
                auth=(self._login, self._password),
            )
        except httpx.HTTPError as exc:
            raise KeywordProviderError(f"{type(exc).__name__}: {exc}".strip(": ")) from exc
        finally:
            if close_client:
                await client.aclose()

        if response.status_code >= 400:
            raise KeywordProviderError(
                f"dataforseo returned status {response.status_code}: {response.text[:200]}"
            )
        try:
            body = response.json()
        except ValueError as exc:
            raise KeywordProviderError(f"failed to parse dataforseo response: {exc}") from exc

        tasks = body.get("tasks") or []
        if body.get("status_code") != 20000 or not tasks:
            raise KeywordProviderError(
                f"dataforseo task failed: {body.get('status_message', 'unknown error')}"
            )
        task = tasks[0]
        if task.get("status_code") != 20000:
            raise KeywordProviderError(
                f"dataforseo task failed: {task.get('status_message', 'unknown error')}"
            )

        metrics: dict[str, KeywordMetrics] = {}
        for row in task.get("result") or []:
            keyword = row.get("keyword")
            if not isinstance(keyword, str) or not keyword:
                continue
            metrics[keyword.strip().lower()] = KeywordMetrics(
                search_volume=int(row.get("search_volume") or 0),
                keyword_difficulty=_coerce_int(row.get("keyword_difficulty")),
                cpc=_coerce_float(row.get("cpc")),
                competition=_normalize_competition(row.get("competition")),
            )
        return metrics


class AutocompleteProvider(KeywordDataProvider):
    """基于 Google suggest 公开端点的免费存在性校验。

    不返回搜索量数值；短语出现在自身的联想列表里即视为真实搜索词，
    以 ``search_volume=None`` + ``competition="confirmed_by_suggest"`` 表达。
    """

    def __init__(
        self,
        *,
        interval_seconds: float = 1.5,
        timeout: float = 10.0,
        rate_limit_backoff_seconds: float = 20.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._interval = max(0.0, interval_seconds)
        self._timeout = timeout
        self._backoff = rate_limit_backoff_seconds
        self._client = client

    async def fetch_metrics(self, phrases: Sequence[str]) -> dict[str, KeywordMetrics]:
        metrics: dict[str, KeywordMetrics] = {}
        if not phrases:
            return metrics
        close_client = False
        client = self._client
        if client is None:
            client = httpx.AsyncClient(timeout=self._timeout)
            close_client = True
        try:
            for index, phrase in enumerate(phrases):
                if index:
                    await asyncio.sleep(self._interval)
                response = await self._fetch_suggest(client, phrase)
                if response is None:
                    raise KeywordRateLimitedError(
                        "google suggest rate limited; retry later",
                        partial=metrics,
                    )
                lowered = phrase.strip().lower()
                if lowered in metrics:
                    continue
                confirmed = _response_confirms(response, lowered)
                if not confirmed:
                    # 原话常含复数（且未必在句尾），标准搜索词多为单数；逐个回查变体。
                    for variant in _singular_variants(phrase):
                        await asyncio.sleep(self._interval)
                        variant_response = await self._fetch_suggest(client, variant)
                        if variant_response is None:
                            raise KeywordRateLimitedError(
                                "google suggest rate limited; retry later",
                                partial=metrics,
                            )
                        if _response_confirms(variant_response, variant.lower()):
                            confirmed = True
                            break
                if confirmed:
                    metrics[lowered] = KeywordMetrics(
                        search_volume=None, competition="confirmed_by_suggest"
                    )
        finally:
            if close_client:
                await client.aclose()
        return metrics

    async def _fetch_suggest(
        self, client: httpx.AsyncClient, phrase: str
    ) -> httpx.Response | None:
        """请求 suggest 端点；被限流时退避一次重试，仍限流返回 None。"""

        params = {
            "client": "firefox",
            "q": phrase,
            # 该端点在中文 locale 下默认返回 GBK 编码，必须显式指定输入/输出编码。
            "ie": "utf-8",
            "oe": "utf-8",
            "hl": "zh-CN" if _CJK_RE.search(phrase) else "en",
        }
        for attempt in range(2):
            response = await client.get(
                "https://suggestqueries.google.com/complete/search", params=params
            )
            if response.status_code != 429:
                break
            if attempt == 0:
                await asyncio.sleep(self._backoff)
        if response.status_code == 429:
            return None
        if response.status_code >= 400:
            raise KeywordProviderError(
                f"google suggest returned status {response.status_code}"
            )
        return response


def _response_confirms(response: httpx.Response, needle: str) -> bool:
    """判断 suggest 响应是否确认 needle 是真实搜索词；解析失败视为未确认。"""

    try:
        body = response.json()
    except ValueError:
        return False
    suggestions = body[1] if isinstance(body, list) and len(body) > 1 else []
    # 联想列表常只包含原词的扩展形式（如 "x converter"），前缀命中即视为确认。
    return any(
        isinstance(item, str)
        and (
            item.strip().lower() == needle or item.strip().lower().startswith(needle)
        )
        for item in suggestions
    )


def _singular_variants(phrase: str) -> list[str]:
    """生成英文短语的单数变体；从最后一个词向前找至多两个可变换词。

    复数不一定在句尾（如 "convert pdfs to excel"），因此对每个可安全
    单数化的位置各生成一个变体，保持其余词不变。
    """

    words = phrase.split()
    variants: list[str] = []
    for index in range(len(words) - 1, -1, -1):
        singular = _word_singular(words[index])
        if singular is None:
            continue
        candidate = words.copy()
        candidate[index] = singular
        variants.append(" ".join(candidate))
        if len(variants) >= 2:
            break
    return variants


def _word_singular(word: str) -> str | None:
    """单个英文词的安全单数化；无法判断时返回 None。"""

    lowered = word.lower()
    if len(lowered) < 4 or not word.isascii() or not word.isalpha():
        return None
    if lowered.endswith(("ss", "us", "is")):
        return None
    if lowered.endswith("ies"):
        return word[:-3] + "y"
    if lowered.endswith(("ches", "shes", "xes", "zes", "ses")):
        return word[:-2]
    if lowered.endswith("s"):
        return word[:-1]
    return None


def resolve_keyword_provider() -> KeywordDataProvider | None:
    """按配置返回可用的关键词数据源：DataForSEO 优先，否则退到免费的 suggest 校验。"""

    settings = get_settings()
    provider = (settings.keyword_provider or "auto").strip().lower()
    if provider == "none":
        return None
    if provider in ("auto", "dataforseo") and (
        settings.dataforseo_api_login and settings.dataforseo_api_password
    ):
        return DataForSEOProvider(
            login=settings.dataforseo_api_login,
            password=settings.dataforseo_api_password,
            sandbox=settings.dataforseo_sandbox,
            timeout=settings.keyword_provider_timeout_seconds,
        )
    if provider in ("auto", "autocomplete"):
        return AutocompleteProvider(
            interval_seconds=settings.keyword_autocomplete_interval_ms / 1000,
            timeout=settings.keyword_provider_timeout_seconds,
        )
    return None


def _coerce_int(value: object) -> int | None:
    if not isinstance(value, (int, float, str)) or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _coerce_float(value: object) -> float | None:
    if not isinstance(value, (int, float, str)) or isinstance(value, bool):
        return None
    try:
        return round(float(value), 4)
    except (TypeError, ValueError):
        return None


def _normalize_competition(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        try:
            score = float(value)
        except (TypeError, ValueError):
            return None
        if score < 0.34:
            return "low"
        if score < 0.67:
            return "medium"
        return "high"
    text = str(value).strip().lower()
    return text or None
