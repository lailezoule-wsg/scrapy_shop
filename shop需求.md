# 多平台电商价格监控系统 — 项目需求

## 一、项目概述

构建一个生产级分布式爬虫系统，监控多个电商平台（当当网、1688、苏宁易购）的商品价格、评价、库存信息，支持增量爬取、反爬对抗、数据清洗入库和实时监控。

---

## 二、环境与版本要求

| 依赖 | 版本要求 | 说明 |
|---|---|---|
| **Python** | `>= 3.12` | 项目最低版本，兼容所有依赖项 |
| **Scrapy** | `>= 2.16` | 最新稳定版，支持 Python 3.10 ~ 3.14 |
| **scrapy-redis** | `>= 0.9.1` | 分布式调度，要求 Scrapy >= 2.0 |
| **scrapy-playwright** | `>= 0.0.48` | JS 渲染，要求 Python >= 3.10 |
| **SQLAlchemy** | `>= 2.0` | ORM 核心，支持 PostgreSQL JSONB / ARRAY |
| **psycopg** | `>= 3.2` | PostgreSQL 驱动（psycopg 3），异步支持 |
| **Redis** | `>= 5.0` | 代理池 / Cookie 池 / 分布式队列 |
| **Playwright** | `>= 1.40` | 浏览器引擎，需 `playwright install` 安装浏览器 |

```bash
# 一键安装核心依赖
pip install "scrapy>=2.16" "scrapy-redis>=0.9.1" "scrapy-playwright>=0.0.48" \
            "SQLAlchemy>=2.0" "psycopg[binary]>=3.2" "redis>=5.0"
playwright install chromium
```

---

## 三、目标平台选型

> 作为个人开发者，核心原则：**反爬适中、数据能拿到、技能点能覆盖**。

### 3.1 候选平台分析

**第一梯队：反爬宽松，适合主力爬取**

| 网站 | 适合原因 | 对应 Spider 类型 |
|---|---|---|
| **当当网** | 反爬最弱，页面结构清晰，有 sitemap | `SitemapSpider` + `CrawlSpider` |
| **苏宁易购** | 反爬中等偏下，部分页面 SSR | `CrawlSpider` |
| **孔夫子旧书网** | 几乎无反爬，适合练手和验证流程 | `Spider`（基础） |

**第二梯队：反爬中等，适合练习中间件与 JS 渲染**

| 网站 | 适合原因 | 对应技能点 |
|---|---|---|
| **1688（阿里批发）** | 比淘宝宽松很多，同属电商场景，有 JS 渲染 | Playwright 渲染、Cookie 池 |
| **拼多多（H5 页面）** | 部分 H5 页反爬比 APP 弱 | `scrapy-playwright`、响应拦截 |
| **小红书（商品笔记）** | 有 JS 渲染，反爬中等 | Playwright + 响应拦截 |

**第三梯队：备选练手站**

| 网站 | 适合原因 | 对应技能点 |
|---|---|---|
| **美团（到店商品）** | 反爬中等，本地生活场景，数据维度丰富 | Pipeline 清洗、数据建模 |
| **唯品会** | 反爬中等，特卖场景数据结构独特 | Pipeline 清洗、数据建模 |

### 3.2 最终选型

```
主力站：当当网        → Spider + CrawlSpider + SitemapSpider
                       → 反爬宽松，专注打磨 Pipeline / ItemLoader

辅助站：1688          → Playwright 渲染 + Cookie 注入
                       → 练习 JS 动态页面处理

分布式站：苏宁易购    → SitemapSpider 增量爬取
                       → 练习分布式 + 多存储写入
```

> **当当网当主力，1688 练反爬，苏宁易购练分布式**——三个站覆盖全部技能点，且全部国内直连。

---

## 四、Scrapy 技能点总览

| 模块 | 功能需求 | 覆盖的 Scrapy 技能点 |
|---|---|---|
| **Spider 层** | 不同平台用不同 Spider 类型 | `Spider`、`CrawlSpider`、`SitemapSpider` |
| **数据建模** | 统一定义商品/评价/店铺数据结构 | `Item`、`Field`、`dataclass` |
| **数据提取** | 结构化清洗、格式化 | `ItemLoader`、`MapCompose`、`TakeFirst`、`Join` |
| **管道处理** | 清洗→校验→去重→多目标存储 | `ItemPipeline`（多级）、`DropItem` |
| **下载中间件** | 代理轮换、UA 池、Cookie 注入、TLS 指纹 | `DownloaderMiddleware` |
| **Spider 中间件** | 按平台过滤、Item 级去重 | `SpiderMiddleware` |
| **信号机制** | 统计爬取指标、优雅关闭连接 | `Signals`（spider_opened/closed、item_scraped） |
| **调度策略** | 增量爬取、优先级队列、限速 | `AUTOTHROTTLE`、`DOWNLOAD_DELAY`、`priority` |
| **分布式** | 多机协同、断点续爬 | `scrapy-redis`、Redis 队列、布隆过滤器 |
| **浏览器渲染** | JS 动态页面（懒加载/滚动加载） | `scrapy-playwright` |
| **数据存储** | 多目标写入 | PostgreSQL（商品主数据 + 结构化报表）、MySQL（价格历史）、Redis（缓存/去重）、ES（全文检索） |
| **运维部署** | 定时任务、监控告警 | Scrapyd、Docker、Prometheus + Grafana |

---

## 五、Spider 层详细设计

### 5.1 Spider 1 — ProductSpider（当当网）

**平台分析**

```
入口：分类列表页 https://category.dangdang.com/cid-{catId}.html
详情：https://product.dangdang.com/{productId}.html

详情页关键 DOM：
  商品名称  → h1.title-p > span::text
  价格      → span.price_p::text（如 "¥59.90"）
  原价      → div.price_info > del::text
  店铺名    → div.shop_name > a::text
  规格参数  → div.prodetail_param > ul > li（"开本:16开" 格式）
  图片      → ul.largePic > img::attr(src)
  分类面包屑 → div.breadcrumb > a::text
```

**实现方案**

```python
class ProductSpider(scrapy.Spider):
    name = "dangdang_product"
    allowed_domains = ["dangdang.com"]
    start_urls = ["https://category.dangdang.com/cid-01.00.00.00.00.00.html"]

    def parse(self, response):
        # 1. 从列表页提取商品详情链接
        for link in response.css("ul.bigimg > li > a.pic::attr(href)"):
            yield response.follow(
                link,
                callback=self.parse_detail,
                cb_kwargs={"category": response.css("div.breadcrumb ::text").getall()[-1]},
                meta={"category_path": response.css("div.breadcrumb a::text").getall()},
            )

        # 2. 翻页
        next_page = response.css("li.next > a::attr(href)").get()
        if next_page:
            yield response.follow(next_page, self.parse)

    def parse_detail(self, response, category):
        # 3. 手动构造价格请求（当当价格走单独接口）
        product_id = response.url.split("/")[-1].split(".")[0]
        price_url = f"https://dangdang.com/price/{product_id}"

        yield response.request.replace(
            url=price_url,
            callback=self.parse_price,
            meta={
                "product_id": product_id,
                "category": category,
                "detail_response": response,
            },
        )

    def parse_price(self, response):
        # 4. 解析价格接口，合并详情数据
        meta = response.meta
        detail = meta["detail_response"]

        yield ProductItem(
            product_id=meta["product_id"],
            title=detail.css("h1.title-p span::text").get(),
            price=response.json().get("price"),
            original_price=detail.css("div.price_info del::text").get(),
            shop_name=detail.css("div.shop_name a::text").get(),
            category=meta["category"],
            platform="dangdang",
            url=detail.url,
            image_urls=detail.css("ul.largePic img::attr(src)").getall(),
            specs=self._parse_specs(detail),
            crawl_time=datetime.now(timezone.utc),
        )
```

**技能点**：`cb_kwargs` 传参、`meta` 跨请求传值、`response.follow` 自动处理相对链接、手动构造 Request 拆分价格接口

### 5.2 Spider 2 — CategoryCrawlSpider（1688）

**平台分析**

```
入口：https://www.1688.com/chanpin/-C8ABB2BFA0.html

列表页：SSR 渲染，商品卡片在 HTML 中
详情页：https://detail.1688.com/offer/{productId}.html
        → 部分字段需要 Playwright 渲染（价格、库存是 JS 动态加载）

分类导航：左侧菜单 → /chanpin/-XXX.html（多级分类）
```

**实现方案**

```python
class CategoryCrawlSpider(CrawlSpider):
    name = "ali1688_category"
    allowed_domains = ["1688.com"]
    start_urls = ["https://www.1688.com/chanpin/-C8ABB2BFA0.html"]

    rules = (
        # Rule 1：跟踪分类导航（只 follow，不解析数据）
        Rule(
            LinkExtractor(allow=r"/chanpin/.*\.html"),
            follow=True,
        ),
        # Rule 2：进入商品详情页
        Rule(
            LinkExtractor(allow=r"/offer/\d+\.html"),
            callback="parse_detail",
        ),
    )

    custom_settings = {
        "DEPTH_LIMIT": 5,
        "DOWNLOAD_DELAY": 2,
        "RANDOMIZE_DOWNLOAD_DELAY": True,
    }

    def parse_detail(self, response):
        product_id = response.css("script::text").re_first(r"offerId['\"]:\s*'(\d+)'")

        item = ProductItem()
        item["product_id"] = product_id
        item["title"] = response.css("h1.title-text::text").get("").strip()
        item["platform"] = "1688"
        item["url"] = response.url
        item["shop_name"] = response.css("div.company-name a::text").get("")
        item["category"] = response.css("div.breadcrumb a::text").getall()[-1]
        item["image_urls"] = response.css("div.tab-pane img::attr(data-lazyload-src)").getall()
        item["crawl_time"] = datetime.now(timezone.utc)

        # 价格字段由 Playwright Spider 补充
        item["price"] = None
        item["original_price"] = None

        specs = {}
        for row in response.css("div.obj-sku div.obj-content > div"):
            key = row.css("span.name::text").get("")
            val = row.css("span.value::text").get("")
            if key and val:
                specs[key.strip()] = val.strip()
        item["specs"] = specs

        yield item
```

**技能点**：`CrawlSpider` + `Rule`、`LinkExtractor` 正则匹配、`follow=True` vs `callback` 分离、`DEPTH_LIMIT` 防无限深入

### 5.3 Spider 3 — SitemapProductSpider（苏宁易购）

**平台分析**

```
Sitemap 入口：https://www.suning.com/sitemap/sitemap-index.xml（索引文件）

格式：
  <url>
    <loc>https://product.suning.com/0000000000/0070066xxx.html</loc>
    <lastmod>2026-07-10</lastmod>
    <changefreq>daily</changefreq>
  </url>

详情页：SSR 渲染，大部分数据在 HTML 中
  商品名称 → div.title-heading > h1::text
  价格     → span.def-price::text
  规格     → div.product-parameter > ul > li
```

**实现方案**

```python
class SitemapProductSpider(SitemapSpider):
    name = "suning_sitemap"
    allowed_domains = ["suning.com"]
    sitemap_urls = ["https://www.suning.com/sitemap/sitemap-index.xml"]

    custom_settings = {
        "DEPTH_LIMIT": 2,
        "DOWNLOAD_DELAY": 1,
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.redis_conn = redis.Redis(host="localhost", port=6379, db=0)
        self.last_crawl = self.redis_conn.get("suning:last_crawl") or "2026-01-01"

    def _parse_sitemap(self, response):
        # 重写父类方法，加入 lastmod 过滤实现增量爬取
        for url in super()._parse_sitemap(response):
            lastmod = response.xpath(
                f"//url[loc='{url}']/lastmod/text()"
            ).get()

            if lastmod and lastmod < self.last_crawl:
                continue  # 跳过未变更的页面

            yield Request(
                url=url,
                callback=self.parse_detail,
                priority=0,  # 全量扫描优先级
                meta={"lastmod": lastmod},
            )

    def parse_detail(self, response):
        product_id = response.url.split("/")[-1].split(".")[0]

        item = ProductItem()
        item["product_id"] = product_id
        item["title"] = response.css("div.title-heading h1::text").get("").strip()
        item["price"] = self._to_float(response.css("span.def-price::text").get())
        item["original_price"] = self._to_float(response.css("span.orig-price::text").get())
        item["shop_name"] = response.css("div.store-name a::text").get("")
        item["category"] = response.css("div.breadcrumb a::text").getall()[-2]
        item["platform"] = "suning"
        item["url"] = response.url
        item["image_urls"] = response.css("div.img-list img::attr(src)").getall()
        item["crawl_time"] = datetime.now(timezone.utc)

        specs = {}
        for li in response.css("div.product-parameter ul li"):
            text = li.css("::text").getall()
            if len(text) >= 2:
                specs[text[0].strip().rstrip("：:")] = text[1].strip()
        item["specs"] = specs

        yield item

    def closed(self, reason):
        # 爬取结束，更新 Redis 时间戳
        self.redis_conn.set("suning:last_crawl", datetime.now().strftime("%Y-%m-%d"))
```

**技能点**：`SitemapSpider` 自动解析 sitemap、增量爬取（lastmod + Redis）、`priority` 优先级、`closed` 信号更新时间戳

### 5.4 三个 Spider 协作关系

```
                    ┌─────────────────┐
                    │  SitemapSpider  │ ← 苏宁易购 sitemap
                    │  全量 URL 发现  │    增量过滤 lastmod
                    └────────┬────────┘
                             │ 产出 product_id 列表
                             ▼
┌──────────────┐    ┌─────────────────┐    ┌──────────────┐
│ ProductSpider│    │  统一数据流     │    │ Category     │
│ 当当网       │───▶│  ProductItem    │───▶│ CrawlSpider  │
│ 详情页精 parse│    │  进入 Pipeline  │    │ 1688 分类遍历│
└──────────────┘    └─────────────────┘    └──────────────┘
                           │
                           ▼
                    ┌──────────────┐
                    │  Pipeline    │
                    │  清洗→校验   │
                    │  →去重→入库  │
                    └──────────────┘
```

---

## 六、数据建模与清洗

### 6.1 Item 定义

```python
class ProductItem(scrapy.Item):
    product_id = scrapy.Field()      # 平台商品ID
    title = scrapy.Field()           # 商品名称
    price = scrapy.Field()           # 当前价格（float）
    original_price = scrapy.Field()  # 原价
    shop_name = scrapy.Field()       # 店铺名
    category = scrapy.Field()        # 分类
    platform = scrapy.Field()        # 来源平台
    url = scrapy.Field()             # 商品链接
    image_urls = scrapy.Field()      # 图片链接列表
    specs = scrapy.Field()           # 规格参数（dict → PostgreSQL JSONB）
    crawl_time = scrapy.Field()      # 爬取时间

class ReviewItem(scrapy.Item):
    product_id = scrapy.Field()
    user = scrapy.Field()
    rating = scrapy.Field()
    content = scrapy.Field()
    date = scrapy.Field()
```

### 6.2 ItemLoader 清洗链

```python
class ProductLoader(ItemLoader):
    default_output_processor = TakeFirst()

    title_in = MapCompose(strip_html, strip_whitespace)
    price_in = MapCompose(strip_currency, to_float)        # "￥299.00" → 299.0
    original_price_in = MapCompose(strip_currency, to_float)
    image_urls_out = Identity()                             # 保留完整列表
    specs_in = MapCompose(parse_spec_string)                # "颜色:红色" → dict
    crawl_time_out = TakeFirst()
```

**技能点**：`Item`/`Field` 定义、`ItemLoader`、输入/输出处理器（`MapCompose`、`TakeFirst`、`Join`、`Identity`）

---

## 七、Pipeline 数据处理链

```
Pipeline 1 — CleanPipeline（优先级 100）
  ├── 去除 HTML 残留标签
  ├── 全角转半角
  ├── 必填字段校验，缺失则 DropItem
  └── Unicode 规范化

Pipeline 2 — ValidatePipeline（优先级 200）
  ├── 价格合理性校验（< 0 或 > 100万 → DropItem + 告警）
  ├── URL 格式校验
  └── 日期字段标准化（dateutil.parser）

Pipeline 3 — DedupPipeline（优先级 300）
  ├── Redis 查询 product_id + platform 是否已存在
  ├── 增量模式：价格未变 → DropItem（不重复入库）
  └── 价格变化 → 更新 change_history

Pipeline 4 — PostgresPipeline（优先级 400）
  ├── 使用 SQLAlchemy ORM 定义表结构（Product / Review）
  ├── specs 字段使用 JSONB 类型存储规格参数
  ├── image_urls 字段使用 ARRAY(Text) 类型存储图片列表
  └── INSERT ... ON CONFLICT(product_id, platform) DO UPDATE 实现 upsert

Pipeline 5 — MySQLPipeline（优先级 500）
  └── 批量写入价格历史表（攒 100 条 flush 一次，使用 SQLAlchemy Core 批量 INSERT）

Pipeline 6 — ESPipeline（优先级 600）
  └── 写入 Elasticsearch（商品名称/分类做全文索引）
```

**技能点**：多级 Pipeline 链、`DropItem`、`from_crawler` 读取配置、`open_spider`/`close_spider` 生命周期、批量写入优化

---

## 八、中间件体系

### 8.1 Downloader Middleware

```python
# 中间件 1：代理轮换
class ProxyMiddleware:
    # Redis 代理池按评分取最优代理
    # 失败自动切换，process_exception 中重试
    # 支持 per-domain 绑定 IP（Sticky Session）

# 中间件 2：UA 池轮换
class RandomUAMiddleware:
    # 维护 50+ 真实浏览器 UA
    # 按平台匹配（当当网用 Chrome UA，1688 用 Firefox UA）

# 中间件 3：Cookie 池注入
class CookiePoolMiddleware:
    # Redis 存储多账号 Cookie
    # process_request 随机注入有效 Cookie
    # process_response 检测 Cookie 失效（302 → 登录页）→ 标记 + 触发重新登录

# 中间件 4：TLS 指纹伪装
class TLSFingerprintMiddleware:
    # 集成 curl_cffi，impersonate="chrome124"
    # 绕过 JA3/JA4 指纹检测

# 中间件 5：重试与降级
class RetryWithFallbackMiddleware:
    # 429 → 指数退避重试
    # 403 → 换代理重试
    # 503 → 延迟重试
    # 3 次失败 → 加入死信队列
```

**技能点**：`process_request`/`process_response`/`process_exception` 三个钩子、中间件优先级、`request.meta` 传递状态

### 8.2 Spider Middleware

```python
class PlatformFilterMiddleware:
    # process_spider_output：按平台过滤不需要的 Item 类型
    # process_start_requests：注入起始 URL 的 platform meta

class ItemDedupMiddleware:
    # process_spider_output：基于 SimHash 做内容相似度去重
    # 防止同一商品在不同分类页重复爬取
```

**技能点**：`process_spider_output`、`process_start_requests`

---

## 九、调度、增量爬取与 JS 渲染

### 9.1 调度策略

```python
# settings.py 核心配置
CONCURRENT_REQUESTS = 32
CONCURRENT_REQUESTS_PER_DOMAIN = 8
DOWNLOAD_DELAY = 0.5
AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_TARGET_CONCURRENCY = 4.0

# 增量爬取
# - Redis 存储每个 product_id 的 last_modified
# - Request 携带 If-Modified-Since / ETag
# - 304 响应 → 跳过解析

# 优先级调度
# - 新商品详情：priority=10
# - 价格复查：  priority=5
# - 全量扫描：  priority=0
```

**技能点**：`AUTOTHROTTLE`、`priority` 优先级、增量爬取（`If-Modified-Since`/`ETag`）、`DEPTH_LIMIT`

### 9.2 JS 渲染（scrapy-playwright）

```python
# 针对懒加载/滚动加载的商品列表页（1688 辅助）
class DynamicProductSpider(scrapy.Spider):
    custom_settings = {
        "DOWNLOAD_HANDLERS": {
            "https": "scrapy_playwright.handler.PlaywrightHandler"
        },
        "PLAYWRIGHT_BROWSER_TYPE": "chromium",
        "PLAYWRIGHT_LAUNCH_OPTIONS": {"headless": True},
    }

    def parse(self, response):
        # 等待商品列表加载完成
        # 模拟滚动触发懒加载
        # 拦截 API 响应直接获取 JSON 数据
        # 从渲染后 DOM 提取数据
```

**技能点**：`scrapy-playwright` 集成、响应拦截、动态页面处理

---

## 十、信号与监控

```python
class CrawlerMonitor:
    # spider_opened  → 初始化 Prometheus Counter/Gauge
    # item_scraped   → 累加爬取计数、按平台分类统计
    # item_dropped   → 记录丢弃原因分布
    # spider_closed  → 生成爬取报告（总数/成功率/耗时/数据量）
    #                → 发送钉钉/邮件告警（失败率 > 阈值时）
```

**技能点**：`signals.connect`、`crawler.stats`、自定义 Extension

---

## 十一、分布式部署

```
架构：
  Master 节点：
    ├── Redis：调度队列 + 布隆过滤器去重 + 代理池 + Cookie 池
    └── Scrapyd：Spider 任务管理

  Worker 节点 × N：
    ├── Scrapy + scrapy-redis（RedisScheduler + RFPDupeFilter）
    ├── Docker 容器化部署
    └── Prometheus exporter → Grafana 监控

  存储节点：
    ├── PostgreSQL（商品主数据 + 结构化报表，JSONB 支持半结构化字段）
    ├── MySQL（价格历史、报表）
    ├── Elasticsearch（商品搜索）
    └── Redis（缓存 + 队列）
```

**技能点**：`scrapy-redis`、`RedisScheduler`、分布式去重（布隆过滤器）、Docker 部署

---

## 十二、Settings 全景

```python
# 项目完整 settings.py 覆盖项
BOT_NAME = "ecommerce_monitor"
ROBOTSTXT_OBEY = True              # 合规
DOWNLOAD_DELAY = 0.5               # 礼貌爬取
CONCURRENT_REQUESTS = 32           # 并发控制
AUTOTHROTTLE_ENABLED = True        # 自适应限速
RETRY_TIMES = 3                    # 重试
RETRY_HTTP_CODES = [500,502,503,408,429]
DOWNLOAD_TIMEOUT = 15              # 超时
COOKIES_ENABLED = False            # 由中间件管理
LOG_LEVEL = "WARNING"              # 日志级别
FEED_EXPORT_ENCODING = "utf-8"     # 导出编码
DUPEFILTER_CLASS = "scrapy_redis.dupefilter.RFPDupeFilter"
SCHEDULER = "scrapy_redis.scheduler.Scheduler"

# PostgreSQL 配置
POSTGRES_HOST = "localhost"
POSTGRES_PORT = 5432
POSTGRES_DB = "ecommerce_monitor"
POSTGRES_USER = "scraper"
POSTGRES_PASSWORD = "****"
SQLALCHEMY_DATABASE_URI = f"postgresql+psycopg://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
```

---

## 十三、技能点覆盖清单

| # | Scrapy 技能点 | 对应章节 |
|---|---|---|
| 1 | Spider（基础） | 5.1 ProductSpider（当当网） |
| 2 | CrawlSpider + Rule + LinkExtractor | 5.2 CategoryCrawlSpider（1688） |
| 3 | SitemapSpider | 5.3 SitemapProductSpider（苏宁易购） |
| 4 | Request / Response / meta / cb_kwargs | 第五章全局 |
| 5 | Item + Field | 6.1 Item 定义 |
| 6 | ItemLoader + Processor | 6.2 ItemLoader 清洗链 |
| 7 | ItemPipeline（多级） | 第七章 Pipeline |
| 8 | DownloaderMiddleware | 8.1 Downloader Middleware |
| 9 | SpiderMiddleware | 8.2 Spider Middleware |
| 10 | Signals + Extension | 第十章 信号与监控 |
| 11 | Settings 全面配置 | 第十二章 Settings |
| 12 | 增量爬取 | 9.1 调度策略 |
| 13 | scrapy-playwright（JS 渲染） | 9.2 JS 渲染 |
| 14 | scrapy-redis（分布式） | 第十一章 分布式部署 |
| 15 | 反爬对抗（代理/UA/Cookie/TLS） | 8.1 Downloader Middleware |
| 16 | 数据存储（PostgreSQL/MySQL/ES/Redis） | 第七章 Pipeline |
| 17 | 部署运维（Scrapyd/Docker/监控） | 第十一章 分布式部署 |

---

## 十四、实施计划

```
Phase 1（1 周）  搭建项目骨架 → Item 建模 → ProductSpider + Pipeline → PostgreSQL 存储（SQLAlchemy ORM + JSONB）
       ↓
Phase 2（1 周）  ItemLoader 清洗链 → 多级 Pipeline → MySQL 批量写入
       ↓
Phase 3（1 周）  DownloaderMiddleware（代理/UA/Cookie）→ 反爬对抗
       ↓
Phase 4（3-5 天）CrawlSpider + SitemapSpider → 多平台覆盖
       ↓
Phase 5（3-5 天）scrapy-playwright → JS 动态页面处理
       ↓
Phase 6（3-5 天）Signals + Extension → 监控统计
       ↓
Phase 7（1 周）  scrapy-redis 分布式改造 → Docker 部署 → Grafana 监控
```
