import asyncio

import httpx
import pytest

from app.db.storage import db
from app.models import FetchStatus, RawEntryStatus
from app.services import raw_entries, rss_fetcher, rss_sources


@pytest.fixture(autouse=True)
def _reset_db() -> None:
    rss_sources.reset_storage()
    yield
    rss_sources.reset_storage()


SAMPLE_RSS = """<?xml version=\"1.0\"?>
<rss version=\"2.0\">
  <channel>
    <title>Example Feed</title>
    <item>
      <title>First Post</title>
      <link>https://example.com/first</link>
      <guid>post-1</guid>
      <description>First summary</description>
      <pubDate>Wed, 01 Nov 2023 12:00:00 GMT</pubDate>
      <category>tech</category>
    </item>
    <item>
      <title>Second Post</title>
      <link>https://example.com/second</link>
      <description><![CDATA[Second summary]]></description>
      <pubDate>Thu, 02 Nov 2023 12:00:00 GMT</pubDate>
      <author>NeedRadar</author>
      <category>rss</category>
      <category>news</category>
    </item>
  </channel>
</rss>
"""

DUPLICATE_CONTENT_RSS = """<?xml version=\"1.0\"?>
<rss version=\"2.0\">
  <channel>
    <title>Dedup Feed</title>
    <item>
      <title>Same Idea</title>
      <link>https://example.com/idea</link>
      <guid>idea-1</guid>
      <description>Build the same tool</description>
    </item>
    <item>
      <title>Same   idea</title>
      <link>https://example.com/idea</link>
      <guid>idea-2</guid>
      <description>Build the same tool</description>
    </item>
  </channel>
</rss>
"""


def test_fetch_rss_source_success_and_deduplicate() -> None:
    async def _run() -> None:
        source = rss_sources.create_source(
            {
                "name": "Example",
                "url": "https://example.com/rss",
                "frequency": 3600,
            }
        )

        def first_handler(request: httpx.Request) -> httpx.Response:
            assert "If-None-Match" not in request.headers
            return httpx.Response(
                200,
                text=SAMPLE_RSS,
                headers={
                    "ETag": '"v1"',
                    "Last-Modified": "Wed, 01 Nov 2023 12:00:00 GMT",
                },
            )

        async with httpx.AsyncClient(transport=httpx.MockTransport(first_handler)) as client:
            result = await rss_fetcher.fetch_rss_source(source.id, client=client)

        assert result.status == FetchStatus.SUCCESS
        assert result.fetched_entries == 2
        assert result.new_entries == 2

        total, entries = raw_entries.list_entries(source_id=source.id)
        assert total == 2
        assert len(entries) == 2
        assert entries[0].title == "Second Post"
        assert sorted(entries[0].tags) == ["news", "rss"]
        assert entries[0].status == RawEntryStatus.PENDING

        updated_source = rss_sources.get_source(source.id)
        assert updated_source.etag == '"v1"'
        assert updated_source.last_fetched_at is not None

        logs = db.list_fetch_logs(source_id=source.id)
        assert len(logs) == 1
        assert logs[0].status == FetchStatus.SUCCESS

        # 第二次抓取返回 304，验证增量逻辑
        def second_handler(request: httpx.Request) -> httpx.Response:
            assert request.headers["If-None-Match"] == '"v1"'
            return httpx.Response(304)

        async with httpx.AsyncClient(transport=httpx.MockTransport(second_handler)) as client:
            second_result = await rss_fetcher.fetch_rss_source(source.id, client=client)

        assert second_result.status == FetchStatus.SUCCESS
        assert second_result.new_entries == 0
        assert second_result.fetched_entries == 0

        logs = db.list_fetch_logs(source_id=source.id)
        assert len(logs) == 2
        assert logs[0].http_status == 304

    asyncio.run(_run())


def test_fetch_rss_source_http_failure() -> None:
    async def _run() -> None:
        source = rss_sources.create_source(
            {
                "name": "Broken",
                "url": "https://example.com/broken",
                "frequency": 3600,
            }
        )

        def handler(_: httpx.Request) -> httpx.Response:
            return httpx.Response(502, text="bad gateway")

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            result = await rss_fetcher.fetch_rss_source(source.id, client=client)

        assert result.status == FetchStatus.FAILURE
        assert result.new_entries == 0
        assert result.error_message is not None and "502" in result.error_message
        total, entries = raw_entries.list_entries(source_id=source.id)
        assert total == 0
        assert entries == []

        logs = db.list_fetch_logs(source_id=source.id)
        assert len(logs) == 1
        assert logs[0].status == FetchStatus.FAILURE
        assert logs[0].http_status == 502

    asyncio.run(_run())


def test_fetch_rss_source_parse_failure() -> None:
    async def _run() -> None:
        source = rss_sources.create_source(
            {
                "name": "Invalid",
                "url": "https://example.com/invalid",
                "frequency": 3600,
            }
        )

        def handler(_: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text="<rss><broken></rss>")

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            result = await rss_fetcher.fetch_rss_source(source.id, client=client)

        assert result.status == FetchStatus.FAILURE
        assert result.new_entries == 0
        assert result.error_message is not None

        logs = db.list_fetch_logs(source_id=source.id)
        assert len(logs) == 1
        assert logs[0].status == FetchStatus.FAILURE
        assert logs[0].http_status == 200

    asyncio.run(_run())


def test_fetch_rss_deduplicates_by_content_hash() -> None:
    async def _run() -> None:
        source = rss_sources.create_source(
            {
                "name": "Dedup",
                "url": "https://example.com/dedup",
                "frequency": 3600,
            }
        )

        def handler(_: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text=DUPLICATE_CONTENT_RSS)

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            result = await rss_fetcher.fetch_rss_source(source.id, client=client)

        assert result.status == FetchStatus.SUCCESS
        assert result.fetched_entries == 2
        assert result.new_entries == 1

        total, entries = raw_entries.list_entries(source_id=source.id)
        assert total == 1
        assert len(entries) == 1
        assert entries[0].guid in {"idea-1", "idea-2"}

    asyncio.run(_run())
