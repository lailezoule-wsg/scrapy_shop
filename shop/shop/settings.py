# Scrapy settings for shop project
#
# For simplicity, this file contains only settings considered important or
# commonly used. You can find more settings consulting the documentation:
#
#     https://docs.scrapy.org/en/latest/topics/settings.html
#     https://docs.scrapy.org/en/latest/topics/downloader-middleware.html
#     https://docs.scrapy.org/en/latest/topics/spider-middleware.html
import os
import sys
import asyncio
from datetime import datetime
from shop.utils.common import clean_old_logs_by_count

# ✅ Windows 上使用 SelectorEventLoop
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

BOT_NAME = "shop"

SPIDER_MODULES = ["shop.spiders"]
NEWSPIDER_MODULE = "shop.spiders"

ADDONS = {}


# Crawl responsibly by identifying yourself (and your website) on the user-agent
#USER_AGENT = "shop (+http://www.yourdomain.com)"

# Obey robots.txt rules
ROBOTSTXT_OBEY = False

# Concurrency and throttling settings
CONCURRENT_REQUESTS = 12
CONCURRENT_REQUESTS_PER_DOMAIN = 6

RANDOM_DOWNLOAD_DELAY = True
DOWNLOAD_DELAY = 1
DOWNLOAD_TIMEOUT = 30

# Disable cookies (enabled by default)
#COOKIES_ENABLED = False

# Disable Telnet Console (enabled by default)
#TELNETCONSOLE_ENABLED = False

# Override the default request headers:
#DEFAULT_REQUEST_HEADERS = {
#    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
#    "Accept-Language": "en",
#}

# Enable or disable spider middlewares
# See https://docs.scrapy.org/en/latest/topics/spider-middleware.html
#SPIDER_MIDDLEWARES = {
#    "shop.middlewares.ShopSpiderMiddleware": 543,
#}

# Enable or disable downloader middlewares
# See https://docs.scrapy.org/en/latest/topics/downloader-middleware.html
DOWNLOADER_MIDDLEWARES = {
   "shop.middlewares.UserAgentMiddleware.UserAgentMiddleware": 300,
}

# Enable or disable extensions
# See https://docs.scrapy.org/en/latest/topics/extensions.html
#EXTENSIONS = {
#    "scrapy.extensions.telnet.TelnetConsole": None,
#}

# Configure item pipelines
# See https://docs.scrapy.org/en/latest/topics/item-pipeline.html
ITEM_PIPELINES = {
   "shop.pipelines.DangDangPipeline.CoverImagePipeline": 480,
   "shop.pipelines.DangDangPipeline.AsyncBatchDataPipeline": 500,
}

# Enable and configure the AutoThrottle extension (disabled by default)
# See https://docs.scrapy.org/en/latest/topics/autothrottle.html
AUTOTHROTTLE_ENABLED = True
# The initial download delay
AUTOTHROTTLE_START_DELAY = 5
# The maximum download delay to be set in case of high latencies
AUTOTHROTTLE_MAX_DELAY = 60
# The average number of requests Scrapy should be sending in parallel to
# each remote server
AUTOTHROTTLE_TARGET_CONCURRENCY = 1.0
# Enable showing throttling stats for every response received:
AUTOTHROTTLE_DEBUG = False

# Enable and configure HTTP caching (disabled by default)
# See https://docs.scrapy.org/en/latest/topics/downloader-middleware.html#httpcache-middleware-settings
#HTTPCACHE_ENABLED = True
#HTTPCACHE_EXPIRATION_SECS = 0
#HTTPCACHE_DIR = "httpcache"
#HTTPCACHE_IGNORE_HTTP_CODES = []
#HTTPCACHE_STORAGE = "scrapy.extensions.httpcache.FilesystemCacheStorage"

# Set settings whose default value is deprecated to a future-proof value
FEED_EXPORT_ENCODING = "utf-8"

POSTGRESQL_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'user': 'postgres',
    'password': 'postgres',
    'database': 'shop',
}

DB_BATCH_SIZE = 10

# scrapy_playwright
DOWNLOAD_HANDLERS = {
    "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
    "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
}
TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"

# 图片配置 固定名称 ImagePipeline会自动获取
IMAGES_STORE = "data/cover_images"
os.makedirs(IMAGES_STORE,exist_ok=True)

# 3. 缩略图配置（可选，会覆盖 Pipeline 中的默认值）
# IMAGES_THUMBS = {
#     'small': (100, 100),
#     'medium': (300, 300),
#     'large': (600, 600),
# }
IMAGES_EXT = ('jpg', 'jpeg', 'png', 'gif')
# 图片最小尺寸过滤（可选） 0 ：不限制
IMAGES_MIN_WIDTH = 0
IMAGES_MIN_HEIGHT = 0
# 有效时间 (每次ImagesPipeline下载图片前执行清理)
IMAGES_EXPIRES = 2

# 日志
# ========== 日志配置 ==========

# ✅ 1. 先定义日志目录
LOG_DIR = 'logs'
os.makedirs(LOG_DIR, exist_ok=True)
clean_old_logs_by_count(LOG_DIR, keep_count=2)
# ✅ 2. 生成带时间戳的日志文件名
LOG_FILE = os.path.join(
    LOG_DIR, 
    f'shop_{datetime.now().strftime("%Y%m%d_%H%M")}.log'
)
# ✅ 3. 日志级别
LOG_LEVEL = 'WARNING'  # 或 'INFO', 'DEBUG', 'ERROR','WARNING'
# ✅ 4. 日志模式（追加）
LOG_FILE_MODE = 'a'
# ✅ 5. 日志编码
LOG_ENCODING = 'utf-8'
# ✅ 6. 日志格式（可选）
LOG_FORMAT = '%(asctime)s [%(name)s] %(levelname)s: %(message)s'
LOG_DATEFORMAT = '%Y-%m-%d %H:%M:%S'

RETRY_ENABLED = True
RETRY_TIMES = 3  # 最多重试 3 次
RETRY_HTTP_CODES = [500, 502, 503, 504, 408, 429, 403]
RETRY_PRIORITY_ADJUST = -1  # 降低重试请求的优先级
