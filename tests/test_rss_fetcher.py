import asyncio
import os

import httpx
import pytest

from app.core import config as config_module
from app.db.storage import db
from app.models import FetchStatus, RawEntryStatus, SourceType
from app.services import raw_entries, rss_fetcher, rss_sources


@pytest.fixture(autouse=True)
def _reset_db() -> None:
    rss_sources.reset_storage()
    yield
    rss_sources.reset_storage()
    config_module.get_settings.cache_clear()
    config_module.settings = config_module.get_settings()
    os.environ.pop("NEEDRADAR_GITHUB_ACCESS_TOKEN", None)
    os.environ.pop("NEEDRADAR_YOUTUBE_API_KEY", None)
    os.environ.pop("NEEDRADAR_REDDIT_ACCESS_TOKEN", None)


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


def test_fetch_hacker_news_source_success() -> None:
    async def _run() -> None:
        source = rss_sources.create_source(
            {
                "name": "Ask HN",
                "url": "https://hacker-news.firebaseio.com/v0/askstories.json",
                "frequency": 900,
                "source_type": SourceType.HACKER_NEWS,
                "config": {"item_limit": 2},
            }
        )

        def handler(request: httpx.Request) -> httpx.Response:
            url = str(request.url)
            if url.endswith("/askstories.json"):
                return httpx.Response(200, json=[101, 102, 103])
            if url.endswith("/item/101.json"):
                return httpx.Response(
                    200,
                    json={
                        "id": 101,
                        "type": "story",
                        "title": "Ask HN: tiny workflow tool wanted",
                        "text": "<p>I need a small tool for recurring admin work.</p>",
                        "by": "alice",
                        "time": 1710000000,
                    },
                )
            if url.endswith("/item/102.json"):
                return httpx.Response(
                    200,
                    json={
                        "id": 102,
                        "type": "story",
                        "title": "Show HN: another prototype",
                        "url": "https://example.com/show-hn",
                        "by": "bob",
                        "time": 1710000500,
                    },
                )
            return httpx.Response(404)

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            result = await rss_fetcher.fetch_rss_source(source.id, client=client)

        assert result.status == FetchStatus.SUCCESS
        assert result.fetched_entries == 2
        assert result.new_entries == 2

        total, entries = raw_entries.list_entries(source_id=source.id)
        assert total == 2
        assert entries[0].source_id == source.id
        assert "askstories" in entries[0].tags
        assert entries[0].status == RawEntryStatus.PENDING

        updated_source = rss_sources.get_source(source.id)
        assert updated_source.last_fetched_at is not None

        logs = db.list_fetch_logs(source_id=source.id)
        assert len(logs) == 1
        assert logs[0].status == FetchStatus.SUCCESS

    asyncio.run(_run())


def test_fetch_github_issues_source_success() -> None:
    async def _run() -> None:
        source = rss_sources.create_source(
            {
                "name": "NeedRadar Issues",
                "url": "https://api.github.com/repos/acme/needradar/issues",
                "frequency": 1800,
                "source_type": SourceType.GITHUB_ISSUES,
                "config": {"item_limit": 5, "state": "open"},
            }
        )

        def handler(request: httpx.Request) -> httpx.Response:
            assert request.headers["Accept"] == "application/vnd.github+json"
            assert request.headers["User-Agent"] == "NeedRadar/0.1"
            assert request.url.params["per_page"] == "5"
            assert request.url.params["state"] == "open"
            return httpx.Response(
                200,
                json=[
                    {
                        "id": 9001,
                        "title": "Need bulk triage helper",
                        "body": "Reviewing issues manually takes too long.",
                        "html_url": "https://github.com/acme/needradar/issues/1",
                        "repository_url": "https://api.github.com/repos/acme/needradar",
                        "created_at": "2024-03-10T10:00:00Z",
                        "state": "open",
                        "user": {"login": "alice"},
                        "labels": [{"name": "automation"}, {"name": "ops"}],
                    },
                    {
                        "id": 9002,
                        "title": "PR should be skipped",
                        "html_url": "https://github.com/acme/needradar/pull/2",
                        "created_at": "2024-03-10T10:05:00Z",
                        "state": "open",
                        "pull_request": {"url": "https://api.github.com/repos/acme/needradar/pulls/2"},
                        "user": {"login": "bob"},
                        "labels": [],
                    },
                ],
            )

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            result = await rss_fetcher.fetch_rss_source(source.id, client=client)

        assert result.status == FetchStatus.SUCCESS
        assert result.fetched_entries == 1
        assert result.new_entries == 1

        total, entries = raw_entries.list_entries(source_id=source.id)
        assert total == 1
        assert entries[0].guid == "9001"
        assert "github_issue" in entries[0].tags
        assert "acme/needradar" in entries[0].tags
        assert "automation" in entries[0].tags
        assert entries[0].author == "alice"

        logs = db.list_fetch_logs(source_id=source.id)
        assert len(logs) == 1
        assert logs[0].status == FetchStatus.SUCCESS

    asyncio.run(_run())


def test_fetch_github_issues_source_rate_limit_failure() -> None:
    async def _run() -> None:
        source = rss_sources.create_source(
            {
                "name": "Rate Limited Issues",
                "url": "https://api.github.com/repos/acme/needradar/issues",
                "frequency": 1800,
                "source_type": SourceType.GITHUB_ISSUES,
                "config": {"item_limit": 5},
            }
        )

        def handler(_: httpx.Request) -> httpx.Response:
            return httpx.Response(
                403,
                headers={"x-ratelimit-remaining": "0"},
                json={"message": "API rate limit exceeded for 127.0.0.1."},
            )

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            result = await rss_fetcher.fetch_rss_source(source.id, client=client)

        assert result.status == FetchStatus.FAILURE
        assert result.error_message == "github api rate limit exceeded; configure NEEDRADAR_GITHUB_ACCESS_TOKEN"

        logs = db.list_fetch_logs(source_id=source.id)
        assert len(logs) == 1
        assert logs[0].status == FetchStatus.FAILURE
        assert logs[0].http_status == 403

    asyncio.run(_run())


def test_fetch_reddit_source_success() -> None:
    async def _run() -> None:
        source = rss_sources.create_source(
            {
                "name": "r/startups new",
                "url": "https://www.reddit.com/r/startups/new",
                "frequency": 1200,
                "source_type": SourceType.REDDIT,
                "config": {"item_limit": 2, "time": "week"},
            }
        )

        def handler(request: httpx.Request) -> httpx.Response:
            assert request.headers["User-Agent"] == "NeedRadar/0.1"
            assert request.url.params["limit"] == "2"
            assert request.url.params["t"] == "week"
            assert "raw_json" not in request.url.params
            assert request.url.path.endswith("/r/startups/new/.rss")
            return httpx.Response(
                200,
                text="""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>t3_abc123</id>
    <title>Need a lightweight client onboarding tool</title>
    <updated>2024-03-20T10:00:00Z</updated>
    <author><name>founder1</name></author>
    <content type="html">&lt;p&gt;Our agency still manages onboarding manually.&lt;/p&gt;</content>
    <link href="https://www.reddit.com/r/startups/comments/abc123/client_onboarding_tool/" />
  </entry>
  <entry>
    <id>t3_def456</id>
    <title>Hiring tracker for small teams</title>
    <updated>2024-03-20T11:00:00Z</updated>
    <author><name>founder2</name></author>
    <content type="html">&lt;p&gt;Still juggling spreadsheets.&lt;/p&gt;</content>
    <link href="https://www.reddit.com/r/startups/comments/def456/hiring_tracker/" />
  </entry>
</feed>""",
            )

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            result = await rss_fetcher.fetch_rss_source(source.id, client=client)

        assert result.status == FetchStatus.SUCCESS
        assert result.fetched_entries == 2
        assert result.new_entries == 2

        total, entries = raw_entries.list_entries(source_id=source.id)
        assert total == 2
        assert entries[0].guid in {"t3_abc123", "t3_def456"}
        assert "reddit" in entries[0].tags
        assert "startups" in entries[0].tags
        assert "reddit_post" in entries[0].tags

        logs = db.list_fetch_logs(source_id=source.id)
        assert len(logs) == 1
        assert logs[0].status == FetchStatus.SUCCESS

    asyncio.run(_run())


def test_fetch_reddit_comments_source_with_signal_tags() -> None:
    async def _run() -> None:
        source = rss_sources.create_source(
            {
                "name": "r/startups comments",
                "url": "https://www.reddit.com/r/startups/comments",
                "frequency": 900,
                "source_type": SourceType.REDDIT,
                "config": {"item_limit": 2, "sort": "new"},
            }
        )

        def handler(request: httpx.Request) -> httpx.Response:
            assert request.headers["User-Agent"] == "NeedRadar/0.1"
            assert request.url.params["limit"] == "2"
            assert request.url.params["sort"] == "new"
            assert request.url.path.endswith("/r/startups/comments/.rss")
            return httpx.Response(
                200,
                text="""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>t1_xyz789</id>
    <title>Comment on onboarding workflow</title>
    <updated>2024-03-20T12:00:00Z</updated>
    <author><name>ops_founder</name></author>
    <summary>I hate how manual onboarding is.</summary>
    <content type="html">&lt;p&gt;I hate how manual onboarding is. Looking for an alternative to Notion for small clients.&lt;/p&gt;</content>
    <link href="https://www.reddit.com/r/startups/comments/post123/comment_xyz789/" />
  </entry>
</feed>""",
            )

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            result = await rss_fetcher.fetch_rss_source(source.id, client=client)

        assert result.status == FetchStatus.SUCCESS
        assert result.fetched_entries == 1
        assert result.new_entries == 1

        total, entries = raw_entries.list_entries(source_id=source.id)
        assert total == 1
        assert entries[0].guid == "t1_xyz789"
        assert entries[0].title == "Comment on onboarding workflow"
        assert "reddit_comment" in entries[0].tags
        assert "complaint_signal" in entries[0].tags
        assert "alternative_request" in entries[0].tags
        assert entries[0].author == "ops_founder"
        assert "manual onboarding" in (entries[0].summary or "").lower()

    asyncio.run(_run())


def test_fetch_reddit_source_uses_json_when_access_token_configured() -> None:
    async def _run() -> None:
        os.environ["NEEDRADAR_REDDIT_ACCESS_TOKEN"] = "reddit-test-token"
        config_module.get_settings.cache_clear()
        config_module.settings = config_module.get_settings()

        source = rss_sources.create_source(
            {
                "name": "r/startups new",
                "url": "https://www.reddit.com/r/startups/new",
                "frequency": 1200,
                "source_type": SourceType.REDDIT,
                "config": {"item_limit": 1, "time": "month"},
            }
        )

        def handler(request: httpx.Request) -> httpx.Response:
            assert request.headers["Authorization"] == "Bearer reddit-test-token"
            assert request.url.params["raw_json"] == "1"
            assert request.url.path.endswith("/r/startups/new.json")
            return httpx.Response(
                200,
                json={
                    "data": {
                        "children": [
                            {
                                "data": {
                                    "name": "t3_ghi789",
                                    "title": "Looking for a better invoicing stack",
                                    "selftext": "QuickBooks feels clunky for our agency.",
                                    "permalink": "/r/startups/comments/ghi789/better_invoicing_stack/",
                                    "author": "agency_ops",
                                    "created_utc": 1711001000,
                                    "subreddit": "startups",
                                    "post_hint": "self",
                                    "is_self": True,
                                    "stickied": False,
                                }
                            }
                        ]
                    }
                },
            )

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            result = await rss_fetcher.fetch_rss_source(source.id, client=client)

        assert result.status == FetchStatus.SUCCESS
        assert result.fetched_entries == 1
        assert result.new_entries == 1

        total, entries = raw_entries.list_entries(source_id=source.id)
        assert total == 1
        assert entries[0].guid == "t3_ghi789"
        assert "reddit_post" in entries[0].tags

    asyncio.run(_run())


def test_fetch_youtube_source_success() -> None:
    async def _run() -> None:
        os.environ["NEEDRADAR_YOUTUBE_API_KEY"] = "youtube-test-key"
        config_module.get_settings.cache_clear()
        config_module.settings = config_module.get_settings()

        source = rss_sources.create_source(
            {
                "name": "YouTube workflow search",
                "url": "https://www.googleapis.com/youtube/v3/search",
                "frequency": 1800,
                "source_type": SourceType.YOUTUBE,
                "config": {"query": "manual workflow automation", "item_limit": 2, "order": "date"},
            }
        )

        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.params["key"] == "youtube-test-key"
            assert request.url.params["q"] == "manual workflow automation"
            assert request.url.params["maxResults"] == "2"
            assert request.url.params["order"] == "date"
            return httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "id": {"videoId": "vid123"},
                            "snippet": {
                                "title": "Automate manual workflow tasks",
                                "description": "A walkthrough for repetitive team operations.",
                                "publishedAt": "2024-04-01T10:00:00Z",
                                "channelTitle": "OpsLab",
                            },
                        },
                        {
                            "id": {"kind": "youtube#channel"},
                            "snippet": {"title": "Skip non-video"},
                        },
                    ]
                },
            )

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            result = await rss_fetcher.fetch_rss_source(source.id, client=client)

        assert result.status == FetchStatus.SUCCESS
        assert result.fetched_entries == 1
        assert result.new_entries == 1

        total, entries = raw_entries.list_entries(source_id=source.id)
        assert total == 1
        assert entries[0].guid == "youtube:vid123"
        assert entries[0].author == "OpsLab"
        assert "youtube" in entries[0].tags

    asyncio.run(_run())
