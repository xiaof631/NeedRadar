import asyncio
import os

import httpx
import pytest

from app.core import config as config_module
from app.db.storage import db
from app.models import FetchStatus, RawEntryStatus, SourceType
from app.services import marketplace_fetcher, raw_entries, rss_fetcher, rss_sources


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

SAMPLE_SXSOFT_HTML = """
<html>
  <body>
    <h2>最新外包项目</h2>
    <table>
      <tr><th>标题</th><th>项目预算</th><th>开发周期</th><th>发布日期</th><th>已有竞标</th></tr>
      <tr>
        <td><a href="/project/1">数据采集分析后台</a></td>
        <td>1千~5千</td>
        <td>7</td>
        <td>2026-04-16</td>
        <td>4</td>
        <td>竞标中</td>
      </tr>
    </table>
    <div>标题 项目预算 开发周期 发布日期 已有竞标</div>
    <div>数据采集与分析</div>
    <div>数据采集分析后台</div>
    <div>1千~5千</div>
    <div>7</div>
    <div>2026-04-16</div>
    <div>4</div>
    <div>竞标中</div>
    <div>标题 项目资金 接包方 开发周期 开工日期</div>
  </body>
</html>
"""

SAMPLE_SXSOFT_FILTER_HTML = """
<html>
  <body>
    <div>标题 项目预算 开发周期 发布日期 已有竞标</div>
    <div>企业应用</div>
    <div>小程序订餐系统开发</div>
    <div>5千~1万</div>
    <div>15</div>
    <div>2026-04-16</div>
    <div>3</div>
    <div>竞标中</div>
    <div>创意设计</div>
    <div>品牌 LOGO 设计</div>
    <div>8百~2千</div>
    <div>5</div>
    <div>2026-04-15</div>
    <div>6</div>
    <div>竞标中</div>
    <div>脚本开发</div>
    <div>游戏脚本代写</div>
    <div>1千~3千</div>
    <div>7</div>
    <div>2026-04-14</div>
    <div>2</div>
    <div>竞标中</div>
    <div>嵌入式与智能硬件</div>
    <div>基于RK3568的openEuler Embedded版本编译java/mysql/qt</div>
    <div>待商议</div>
    <div>20</div>
    <div>2026-04-13</div>
    <div>1</div>
    <div>竞标中</div>
    <div>标题 项目资金 接包方 开发周期 开工日期</div>
  </body>
</html>
"""

SAMPLE_ZBJ_HTML = """
<div class="task-list-content j-scrollcontent">
  <div class="task-list-item" data-tid="1920346">
    <p class="task-title"><span class="orange">￥4320</span> 重庆：游轮公司征集LOGO设计</p>
    <p class="task-detail"><span class="fr">24天完成</span><span class="fl">326个服务商参与</span></p>
  </div>
</div>
<ul>
  <li>
    <a href="//task.zbj.com/5771984/" title="易债中国—民间债权登记系统开发" target="_blank"></a>
    <div class="hall-floor-main-footer">
      <p class="title"><span class="orange">￥100000</span>&nbsp;&nbsp;<a href="//task.zbj.com/5771984/" title="易债中国—民间债权登记系统开发" target="_blank">易债中国—民间债权登记...</a></p>
      <p class="state"><span class="state state-choosing">选标中</span><span class="time"></span></p>
    </div>
  </li>
</ul>
"""

SAMPLE_PPH_HTML = """
<ul>
  <li class="list__item⤍List⤚2ytmm">
    <div class="item⤍ListItem⤚1iGUH item--container⤍ListItem⤚2wpiz">
      <div class="card__meta⤍ListItem⤚3wkEV">
        <div class="card__user⤍ListItem⤚3sK3s">
          <span class="card__username-container⤍ListItem⤚2kPGk"><span class="u-txt--crop">by<span class="card__username⤍ListItem⤚QnBBG">&nbsp;Raj S.</span></span></span>
        </div>
        <div class="u-txt--right card__price⤍ListItem⤚3VxJ9"><span class="title-nano"><div><span>$203</span></div></span></div>
      </div>
      <h6 class="item__title⤍ListItem⤚2FRMT"><a class="item__url⤍ListItem⤚20ULx" href="https://www.peopleperhour.com/freelance-jobs/technology-programming/front-end-development/frontend-developer-react-next-js-4488000">Frontend Developer (React / Next.js)</a></h6>
      <p class="item__desc⤍ListItem⤚3f4JV">Early-stage startup seeks a proactive Frontend Developer (React/Next.js) to own features end-to-end.</p>
      <div class="card__footer⤍ListItem⤚1KHhv"><div class="nano card__footer-left⤍ListItem⤚16Odv"><span>1 day ago</span><span class="u-mgl--1">57 proposals</span><span class="u-mgl--1"><span><i class="fpph fpph-location"></i>Remote</span></span></div></div>
    </div>
  </li>
</ul>
"""

SAMPLE_WWR_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>We Work Remotely: Remote jobs in design, programming, marketing and more</title>
    <item>
      <title>Sanctuary Computer: Senior Frontend Developer (Contract)</title>
      <region>Anywhere in the World</region>
      <category>Front-End Programming</category>
      <description><![CDATA[
        <p><strong>Headquarters:</strong> New York City</p>
        <p>We are hiring a contract-based Senior Frontend Developer for client projects.</p>
        <p>Compensation ranges from $100/hr to $130/hr.</p>
      ]]></description>
      <pubDate>Fri, 27 Mar 2026 16:28:28 +0000</pubDate>
      <guid>https://weworkremotely.com/remote-jobs/sanctuary-computer-senior-frontend-developer-1</guid>
      <link>https://weworkremotely.com/remote-jobs/sanctuary-computer-senior-frontend-developer-1</link>
    </item>
  </channel>
</rss>
"""

SAMPLE_REMOTIVE_JSON = """{
  "job-count": 2,
  "jobs": [
    {
      "id": 2001,
      "url": "https://remotive.com/remote-jobs/software-dev/senior-frontend-engineer-contract-2001",
      "title": "Senior Frontend Engineer (Contract)",
      "company_name": "Acme Labs",
      "category": "Software Development",
      "job_type": "contract",
      "publication_date": "2026-04-16T09:30:00",
      "candidate_required_location": "Worldwide",
      "salary": "$100,000 - $120,000",
      "description": "<p>Build and ship React interfaces for a B2B SaaS platform.</p>",
      "tags": ["React", "TypeScript", "Frontend"]
    },
    {
      "id": 2002,
      "url": "https://remotive.com/remote-jobs/software-dev/full-time-backend-engineer-2002",
      "title": "Backend Engineer",
      "company_name": "Northwind",
      "category": "Software Development",
      "job_type": "full_time",
      "publication_date": "2026-04-15T10:00:00",
      "candidate_required_location": "USA",
      "salary": "$130,000 - $150,000",
      "description": "<p>Join our full-time backend team.</p>",
      "tags": ["Python", "API", "Backend"]
    }
  ]
}"""

SAMPLE_JOBICY_JSON = """{
  "apiVersion": "2.2.13",
  "jobCount": 2,
  "jobs": [
    {
      "id": 3001,
      "url": "https://jobicy.com/jobs/3001-senior-python-developer-code-migration-specialist",
      "jobTitle": "Senior Python Developer – Code Migration Specialist",
      "companyName": "Mindrift",
      "jobIndustry": ["Software Engineering"],
      "jobType": ["Full-Time"],
      "jobGeo": "Philippines",
      "jobLevel": "Senior",
      "jobExcerpt": "Participation is project-based, not permanent employment.",
      "jobDescription": "<p>Freelance project-based collaboration for a senior Python developer. 20-30 hours per week.</p>",
      "pubDate": "2026-04-15T11:44:40+00:00",
      "salaryMin": 24000,
      "salaryCurrency": "USD",
      "salaryPeriod": "yearly"
    },
    {
      "id": 3002,
      "url": "https://jobicy.com/jobs/3002-full-stack-web-developer",
      "jobTitle": "Full Stack Web Developer",
      "companyName": "CIAT",
      "jobIndustry": ["Programming"],
      "jobType": ["Full-Time"],
      "jobGeo": "USA",
      "jobLevel": "Any",
      "jobExcerpt": "Remote full-time web developer role.",
      "jobDescription": "<p>Employment Type: Full-time</p>",
      "pubDate": "2026-04-15T10:44:40+00:00",
      "salaryMin": 85000,
      "salaryMax": 95000,
      "salaryCurrency": "USD",
      "salaryPeriod": "yearly"
    }
  ],
  "success": true
}"""


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


@pytest.mark.parametrize(
    ("detail", "expected_budget", "expected_timeline"),
    [
        ("$25 - $50/hr45 hrs/wkDuration: Ongoing", "$25 - $50/hr", "45 hrs/wk | Duration: Ongoing"),
        ("$500 - $1,000One-timeDelivery time: 1 week", "$500 - $1,000", "One-time | Delivery time: 1 week"),
        ("$5,000 - $10,000/moDuration: Ongoing(GMT -5) EST", "$5,000 - $10,000/mo", "Duration: Ongoing (GMT -5) EST"),
    ],
)
def test_split_budget_timeline_for_contra(detail: str, expected_budget: str, expected_timeline: str) -> None:
    budget, timeline = marketplace_fetcher._split_budget_timeline(detail)

    assert budget == expected_budget
    assert timeline == expected_timeline


def test_parse_zbj_marketplace_listing() -> None:
    source = rss_sources.create_source(
        {
            "name": "猪八戒需求大厅精选任务",
            "url": "https://task.zbj.com/index/",
            "frequency": 3600,
            "source_type": SourceType.FREELANCE_MARKETPLACE,
            "config": {
                "adapter": "zbj_hall_scroll",
                "item_limit": 10,
                "include_keywords": "开发,搭建,定制,实现,对接,小程序,网站,系统,平台,插件,程序,前端,后端,数据库,进销存,erp,crm,saas,web,软件,app,android,ios,管理软件",
                "exclude_keywords": "logo,海报,文案,命名,台标,梳子,造句,展区设计,外观设计,广告,节目方案,创意设计,包装设计,活动,征集,大赛,推广,运营",
            },
        }
    )

    items = marketplace_fetcher._filter_marketplace_items(
        source,
        marketplace_fetcher._parse_marketplace_page(source, SAMPLE_ZBJ_HTML),
    )

    assert len(items) == 1
    item = items[0]
    assert item.guid == "zbj:5771984"
    assert item.title == "易债中国—民间债权登记系统开发"
    assert item.link == "https://task.zbj.com/5771984/"
    assert item.metadata["platform"] == "猪八戒"
    assert item.metadata["budget"] == "￥100000"
    assert item.metadata["timeline"] == "选标中"
    assert item.metadata["location"] is None
    assert item.description == "选标中"


def test_parse_peopleperhour_marketplace_listing() -> None:
    source = rss_sources.create_source(
        {
            "name": "PeoplePerHour Technology Projects",
            "url": "https://www.peopleperhour.com/freelance-jobs/technology-programming",
            "frequency": 3600,
            "source_type": SourceType.FREELANCE_MARKETPLACE,
            "config": {
                "adapter": "peopleperhour_technology",
                "item_limit": 10,
                "include_keywords": "developer,development,software,website,web,frontend,backend,full-stack,full stack,react,next.js,python,django,api,cms,erp,crm,database,automation,android,ios,wordpress,app",
                "exclude_keywords": "logo,branding,illustration,copywriting,video,marketing,social media,seo only,design only",
            },
        }
    )

    items = marketplace_fetcher._filter_marketplace_items(
        source,
        marketplace_fetcher._parse_marketplace_page(source, SAMPLE_PPH_HTML),
    )

    assert len(items) == 1
    item = items[0]
    assert item.title == "Frontend Developer (React / Next.js)"
    assert item.author == "Raj S."
    assert item.metadata["platform"] == "PeoplePerHour"
    assert item.metadata["budget"] == "$203"
    assert item.metadata["location"] == "Remote"
    assert item.metadata["bids"] == "57"


def test_parse_weworkremotely_programming_rss() -> None:
    source = rss_sources.create_source(
        {
            "name": "We Work Remotely Programming Contracts",
            "url": "https://weworkremotely.com/categories/remote-programming-jobs.rss",
            "frequency": 3600,
            "source_type": SourceType.FREELANCE_MARKETPLACE,
            "config": {
                "adapter": "wwr_programming_rss",
                "item_limit": 10,
                "include_keywords": "contract,contract-based,freelance,project-based,/hr,hourly",
                "exclude_keywords": "intern,marketing,sales,designer,design",
            },
        }
    )

    items = marketplace_fetcher._filter_marketplace_items(
        source,
        marketplace_fetcher._parse_marketplace_page(source, SAMPLE_WWR_RSS),
    )

    assert len(items) == 1
    item = items[0]
    assert item.title == "Senior Frontend Developer (Contract)"
    assert item.author == "Sanctuary Computer"
    assert item.metadata["platform"] == "We Work Remotely"
    assert item.metadata["engagement"] == "contract"
    assert item.metadata["budget"] == "$100/hr to $130/hr"
    assert item.metadata["location"] == "Anywhere in the World"


def test_parse_remotive_api_contract_jobs() -> None:
    source = rss_sources.create_source(
        {
            "name": "Remotive Software Contracts",
            "url": "https://remotive.com/api/remote-jobs?category=software-dev&limit=40",
            "frequency": 21600,
            "source_type": SourceType.FREELANCE_MARKETPLACE,
            "config": {
                "adapter": "remotive_api",
                "item_limit": 10,
                "job_types": "contract,freelance",
                "include_keywords": "contract,freelance,developer,engineer,frontend,backend,react,next.js,python,django,api",
                "exclude_keywords": "intern,designer,design,sales,marketing,talent pool,talent community",
            },
        }
    )

    items = marketplace_fetcher._filter_marketplace_items(
        source,
        marketplace_fetcher._parse_marketplace_page(source, SAMPLE_REMOTIVE_JSON),
    )

    assert len(items) == 1
    item = items[0]
    assert item.title == "Senior Frontend Engineer (Contract)"
    assert item.author == "Acme Labs"
    assert item.link == "https://remotive.com/remote-jobs/software-dev/senior-frontend-engineer-contract-2001"
    assert item.metadata["platform"] == "Remotive"
    assert item.metadata["engagement"] == "contract"
    assert item.metadata["budget"] == "$100,000 - $120,000"
    assert item.metadata["location"] == "Worldwide"
    assert item.metadata["skills"] == ["React", "TypeScript", "Frontend"]


def test_parse_jobicy_api_contract_jobs() -> None:
    source = rss_sources.create_source(
        {
            "name": "Jobicy Contract Developer Roles",
            "url": "https://jobicy.com/api/v2/remote-jobs?count=100&tag=developer",
            "frequency": 21600,
            "source_type": SourceType.FREELANCE_MARKETPLACE,
            "config": {
                "adapter": "jobicy_api",
                "item_limit": 10,
                "exclude_keywords": "trainer,data scientist,data science,analyst,physics,chemistry,civil engineer,mathematics",
            },
        }
    )

    items = marketplace_fetcher._filter_marketplace_items(
        source,
        marketplace_fetcher._parse_marketplace_page(source, SAMPLE_JOBICY_JSON),
    )

    assert len(items) == 1
    item = items[0]
    assert item.title == "Senior Python Developer – Code Migration Specialist"
    assert item.author == "Mindrift"
    assert item.link == "https://jobicy.com/jobs/3001-senior-python-developer-code-migration-specialist"
    assert item.metadata["platform"] == "Jobicy"
    assert item.metadata["engagement"] == "hourly-contract"
    assert item.metadata["budget"] == "$24,000+/yearly"
    assert item.metadata["location"] == "Philippines"
    assert "python" in item.metadata["skills"]


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


def test_fetch_marketplace_source_success() -> None:
    async def _run() -> None:
        source = rss_sources.create_source(
            {
                "name": "软件项目交易网最新外包项目",
                "url": "https://www.sxsoft.com/",
                "frequency": 3600,
                "source_type": SourceType.FREELANCE_MARKETPLACE,
                "config": {"adapter": "sxsoft_latest", "item_limit": 5},
            }
        )

        def handler(_: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text=SAMPLE_SXSOFT_HTML)

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            result = await rss_fetcher.fetch_rss_source(source.id, client=client)

        assert result.status == FetchStatus.SUCCESS
        assert result.fetched_entries == 1
        assert result.new_entries == 1

        total, entries = raw_entries.list_entries(source_id=source.id)
        assert total == 1
        assert entries[0].title == "数据采集分析后台"
        assert entries[0].metadata["platform"] == "软件项目交易网"
        assert entries[0].metadata["budget"] == "1千~5千"
        assert entries[0].metadata["category"] == "数据采集与分析"
        assert entries[0].link == "https://www.sxsoft.com/project/1"

    asyncio.run(_run())


def test_fetch_remotive_marketplace_source_success() -> None:
    async def _run() -> None:
        source = rss_sources.create_source(
            {
                "name": "Remotive Software Contracts",
                "url": "https://remotive.com/api/remote-jobs?category=software-dev&limit=40",
                "frequency": 21600,
                "source_type": SourceType.FREELANCE_MARKETPLACE,
                "config": {
                    "adapter": "remotive_api",
                    "item_limit": 5,
                    "job_types": "contract,freelance",
                },
            }
        )

        def handler(_: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text=SAMPLE_REMOTIVE_JSON, headers={"content-type": "application/json"})

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            result = await rss_fetcher.fetch_rss_source(source.id, client=client)

        assert result.status == FetchStatus.SUCCESS
        assert result.fetched_entries == 1
        assert result.new_entries == 1

        total, entries = raw_entries.list_entries(source_id=source.id)
        assert total == 1
        assert entries[0].title == "Senior Frontend Engineer (Contract)"
        assert entries[0].metadata["platform"] == "Remotive"
        assert entries[0].metadata["engagement"] == "contract"
        assert entries[0].author == "Acme Labs"

    asyncio.run(_run())


def test_fetch_jobicy_marketplace_source_success() -> None:
    async def _run() -> None:
        source = rss_sources.create_source(
            {
                "name": "Jobicy Contract Developer Roles",
                "url": "https://jobicy.com/api/v2/remote-jobs?count=100&tag=developer",
                "frequency": 21600,
                "source_type": SourceType.FREELANCE_MARKETPLACE,
                "config": {
                    "adapter": "jobicy_api",
                    "item_limit": 5,
                },
            }
        )

        def handler(_: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text=SAMPLE_JOBICY_JSON, headers={"content-type": "application/json"})

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            result = await rss_fetcher.fetch_rss_source(source.id, client=client)

        assert result.status == FetchStatus.SUCCESS
        assert result.fetched_entries == 1
        assert result.new_entries == 1

        total, entries = raw_entries.list_entries(source_id=source.id)
        assert total == 1
        assert entries[0].title == "Senior Python Developer – Code Migration Specialist"
        assert entries[0].metadata["platform"] == "Jobicy"
        assert entries[0].metadata["engagement"] == "hourly-contract"
        assert entries[0].author == "Mindrift"

    asyncio.run(_run())


def test_parse_sxsoft_marketplace_listing_filters_non_software_projects() -> None:
    source = rss_sources.create_source(
        {
            "name": "软件项目交易网最新外包项目",
            "url": "https://www.sxsoft.com/",
            "frequency": 3600,
            "source_type": SourceType.FREELANCE_MARKETPLACE,
            "config": {
                "adapter": "sxsoft_latest",
                "item_limit": 12,
                "topic": "software-development",
                "include_keywords": "开发,搭建,定制,实现,对接,小程序,网站,系统,平台,插件,程序,前端,后端,后台,数据库,进销存,erp,crm,saas,web,软件,app,android,ios,管理软件,qt,java,mysql",
                "exclude_keywords": "logo,海报,文案,命名,广告,创意设计,包装设计,活动,征集,大赛,推广,运营,设计,ui,优化,协议,脚本,代付",
            },
        }
    )

    items = marketplace_fetcher._filter_marketplace_items(
        source,
        marketplace_fetcher._parse_marketplace_page(source, SAMPLE_SXSOFT_FILTER_HTML),
    )

    assert len(items) == 2
    titles = [item.title for item in items]
    assert titles == ["小程序订餐系统开发", "基于RK3568的openEuler Embedded版本编译java/mysql/qt"]
    assert items[0].metadata["category"] == "企业应用"


def test_normalize_keywords_lowercases_values() -> None:
    keywords = marketplace_fetcher._normalize_keywords("Web,APP,嵌入式")

    assert keywords == ["web", "app", "嵌入式"]


def test_filter_marketplace_items_requires_each_keyword_group() -> None:
    source = rss_sources.create_source(
        {
            "name": "DocReview test source",
            "url": "https://example.com/jobs",
            "frequency": 3600,
            "source_type": SourceType.FREELANCE_MARKETPLACE,
            "config": {
                "include_keyword_groups": "pdf,document,invoice;extract,parse,review",
                "exclude_keywords": "logo",
            },
        }
    )
    matching = marketplace_fetcher.ParsedMarketplaceLead(
        guid="match",
        title="PDF invoice extraction workflow",
        summary="Extract fields from invoices and review them before export.",
        description=None,
        link=None,
        published_at=None,
        author=None,
    )
    missing_action = marketplace_fetcher.ParsedMarketplaceLead(
        guid="missing-action",
        title="PDF invoice archive",
        summary="Store scanned invoices in a folder.",
        description=None,
        link=None,
        published_at=None,
        author=None,
    )
    excluded = marketplace_fetcher.ParsedMarketplaceLead(
        guid="excluded",
        title="PDF logo extraction",
        summary="Extract a logo from a PDF.",
        description=None,
        link=None,
        published_at=None,
        author=None,
    )

    items = marketplace_fetcher._filter_marketplace_items(
        source,
        [matching, missing_action, excluded],
    )

    assert [item.guid for item in items] == ["match"]


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
