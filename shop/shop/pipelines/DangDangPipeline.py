# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html


# useful for handling different item types with a single interface
from os import PathLike
from typing_extensions import Self

import asyncpg
import hashlib
import scrapy
from itemadapter import ItemAdapter
from scrapy.crawler import Crawler
from shop.items.DangDangItem import BooksItem
from scrapy.exceptions import DropItem
from scrapy.pipelines.images import ImagesPipeline,ImageException
from scrapy.pipelines.media import  MediaPipeline
from scrapy.http import Request, Response
from twisted.python.failure import Failure
from scrapy.pipelines.files import FileException

class CoverImagePipeline(ImagesPipeline):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.config_ext = self.crawler.settings.get("IMAGES_EXT",('jpg', 'jpeg', 'png', 'gif'))

    """封面图下载"""
    def get_media_requests(self,item,info) :  # type: ignore[override]
        adapter = ItemAdapter(item)
        cover_image = adapter.get('cover_image', [])
        info.spider.logger.warning(f"🚄🚄🚄🚄 封面图下载:{cover_image}")
        if not cover_image:
            return []
        # 确保是列表
        if isinstance(cover_image, str):
            cover_image = [cover_image]
        for index, url in enumerate(cover_image):
            if not url:
                continue
            yield scrapy.Request(
                    url,
                    meta={
                        'item': dict(adapter),
                        'index': index,
                    }
                )
    # scrapy 会根据file_path 的返回路径是否存在缓存中 确定是否要重新下载
    def file_path(self, request, response=None, info=None, *, item=None):
        """自定义图片保存路径和文件名"""
        # 从 URL 提取扩展名
        extension = request.url.split('.')[-1]
        if extension not in self.config_ext:
            extension = 'jpg'
        return f'{hashlib.md5(request.url.encode()).hexdigest()[:8]}.{extension}'
    def item_completed(self, results, item, info):
        """当所有图片下载完成后调用，results 是一个列表，每个元素为 (success, data)"""
        # results: [(True, {'url': ..., 'path': ..., 'checksum': ...}), (False, ...)]
        adapter = ItemAdapter(item)
         # 提取成功下载的本地路径
        local_paths = []
        try:
            # results 元组列表 [(success,data),(success,data),(success,data)]  success: bool  data:dict | Failure
            for success, data in results:
                if success and isinstance(data, dict):
                    local_paths.append(data['path'])
                    info.spider.logger.warning(f"🚄🚄🚄🚄图片下载成功: {data}")
                else:
                    # 失败或数据异常
                    if isinstance(data, Failure):
                        # 获取异常类型和异常消息
                        exc_type = data.type           # 异常类，如 FileException
                        exc_value = data.value         # 异常实例
                        # exc_traceback = data.getTraceback()  # 完整堆栈字符串
                        info.spider.logger.error(f"🚄🚄🚄🚄图片下载失败: {type(data.value).__name__}: {exc_value}")
                    else:
                        info.spider.logger.warning(f"🚄🚄🚄🚄图片下载失败3: {data}")
        except FileException as e:
            info.spider.logger.warning(f"🚄🚄🚄🚄图片下载失败: {str(e)}")
            pass
        except Exception as e:
            info.spider.logger.warning(f"🚄🚄🚄🚄图片下载失败: {str(e)}")
            pass
        # 将本地路径列表保存到 item 中
        # 获取原始字段，并设置默认值为空列表
        if local_paths:
            # 如果原始字段是单个字符串，这里保存第一个路径
            # 如果原始是列表，则保存列表
            original = adapter.get('cover_image')
            if isinstance(original, str):
                adapter['cover_image_local'] = local_paths[0] if local_paths else ''
            else:
                adapter['cover_image_local'] = ",".join(local_paths)
        else:
            adapter['cover_image_local'] = ""
        return item
    
class AsyncBatchDataPipeline:
    TABLE_CONFIG = {
        BooksItem: {
            "table": "dangdang_books",
            "columns": ["product_id","title", "url", "author", "cover_image", "cover_image_local", 
                        "price", "publisher", "description", "published_at"],
            "conflict_column": "product_id",
            "update_columns": ["title", "url", "author", "cover_image", "cover_image_local", 
                            "price", "publisher", "description", "published_at","updated_at"],
            "create_sql": """
                CREATE TABLE IF NOT EXISTS dangdang_books (
                    id BIGSERIAL PRIMARY KEY,
                    product_id BIGSERIAL NOT NULL,
                    title VARCHAR(500) NOT NULL,
                    url VARCHAR(512) NOT NULL UNIQUE,
                    author VARCHAR(100) DEFAULT NULL,
                    cover_image VARCHAR(512) DEFAULT NULL,
                    cover_image_local VARCHAR(512) DEFAULT NULL,
                    price DECIMAL(12,2) DEFAULT 0.00,
                    publisher VARCHAR(50) DEFAULT NULL,
                    description TEXT,
                    published_at TIMESTAMP DEFAULT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                
                -- 创建索引（可选）
                CREATE INDEX IF NOT EXISTS idx_dangdang_books_title ON dangdang_books(title);
                CREATE UNIQUE INDEX IF NOT EXISTS idx_dangdang_books_product_id ON dangdang_books(product_id);
            """
        }
    }
    def __init__(self,config,batch_size):
        self.config = config
        self.batch_size = batch_size
        self.pool = None
        self._cache = {}                      # {item_cls: [ (values, item), ... ]}
        self._sql_templates = {}              # 缓存各表的预编译SQL模板

    @classmethod
    def from_crawler(cls,crawler):
        config = crawler.settings.get("POSTGRESQL_CONFIG")
        if not config:
            raise ValueError("POSTGRESQL_CONFIG not found in settings")
        batch_size = crawler.settings.get('DB_BATCH_SIZE', 100)
        return cls(config,batch_size)
    
    async def open_spider(self,spider):
        self.pool = await asyncpg.create_pool(
            **self.config,
            min_size=5,
            max_size=20,
            command_timeout=60,
            max_inactive_connection_lifetime=300,
        )
        spider.logger.info(f"Connected to PostgreSQL: {self.config.get('database')}")
        # 建表（可考虑移到外部，但保留在这里也可以）
        async with self.pool.acquire() as conn:
            for item_cls, cfg in self.TABLE_CONFIG.items():
                create_sql = cfg.get("create_sql")
                if create_sql:
                    await conn.execute(create_sql)
                    spider.logger.info(f"Table {cfg['table']} checked/created.")

    async def close_spider(self,spider):
        """关闭前刷新所有缓存"""
        await self._flush_all(spider)
        if self.pool:
            await self.pool.close()
            spider.logger.info("PostgreSQL connection pool closed.")

    async def process_item(self, item, spider):
        """将 Item 加入缓存，达到阈值时刷新"""
        item_cls = type(item)
        cfg = self.TABLE_CONFIG.get(item_cls)
        if not cfg:
            spider.logger.warning(f"No table config for {item_cls.__name__}, dropping item")
            raise DropItem(f"No table config for {item_cls.__name__}")

        # 提取字段和值
        col_config = cfg["columns"]
        if isinstance(col_config, list):
            columns = col_config
            item_fields = col_config
        elif isinstance(col_config, dict):
            columns = list(col_config.values())
            item_fields = list(col_config.keys())
        else:
            raise TypeError(f"Invalid columns config for {cfg['table']}")

        # 提取值（此处可做类型转换，如 list -> str）
        adapter = ItemAdapter(item)
        values = [adapter.get(field) for field in item_fields]

        # 存入缓存
        cache_key = item_cls
        if cache_key not in self._cache:
            self._cache[cache_key] = []
        self._cache[cache_key].append((values, item))  # 保存 item 用于日志

        # 达到阈值则刷新该类型
        if len(self._cache[cache_key]) >= self.batch_size:
            await self._flush(cache_key, spider)

        return item

    async def _flush(self, item_cls, spider):
        """批量写入指定类型的缓存数据"""
        cache = self._cache.get(item_cls, [])
        if not cache:
            return

        cfg = self.TABLE_CONFIG[item_cls]
        table = cfg["table"]
        columns = cfg["columns"] if isinstance(cfg["columns"], list) else list(cfg["columns"].values())
        conflict_col = cfg.get("conflict_column")
        update_cols = cfg.get("update_columns", [])

        # 构造批量插入 SQL（一次执行多行）
        sql = self._build_batch_insert_sql(table, columns, conflict_col, update_cols, len(cache))
        # 展平所有参数
        flat_params = []
        for values, _ in cache:
            flat_params.extend(values)

        assert self.pool is not None, "Pool not initialized"

        try:
            async with self.pool.acquire() as conn:
                await conn.execute(sql, *flat_params)
            spider.logger.debug(f"Batch inserted {len(cache)} rows into {table}")
        except Exception as e:
            spider.logger.error(f"Batch insert failed for {table}: {e}")
            # 可选：降级为逐条插入（或记录失败数据）
            # 此处直接抛出，中断爬虫（可根据需要改为重试或丢弃）
            raise
        finally:
            # 清空缓存
            self._cache[item_cls] = []

    def _build_batch_insert_sql(self, table, columns, conflict_col, update_cols, batch_size):
        """生成批量插入 SQL，包含 ON CONFLICT 子句"""
        num_cols = len(columns)
        # 构造 VALUES 部分: ($1, $2, ...), ($3, $4, ...), ...
        value_parts = []
        param_idx = 1
        for _ in range(batch_size):
            placeholders = ', '.join([f'${param_idx + i}' for i in range(num_cols)])
            value_parts.append(f'({placeholders})')
            param_idx += num_cols

        sql = f"INSERT INTO {table} ({', '.join(columns)}) VALUES {', '.join(value_parts)}"

        if conflict_col:
            if update_cols:
                set_clauses = []
                for col in update_cols:
                    if col == "updated_at":
                        set_clauses.append(f"{col} = CURRENT_TIMESTAMP")
                    else:
                        set_clauses.append(f"{col} = EXCLUDED.{col}")
                sql += f" ON CONFLICT ({conflict_col}) DO UPDATE SET {', '.join(set_clauses)}"
            else:
                sql += f" ON CONFLICT ({conflict_col}) DO NOTHING"
        return sql

    async def _flush_all(self, spider):
        """刷新所有类型的缓存"""
        for item_cls in list(self._cache.keys()):
            if self._cache.get(item_cls):
                await self._flush(item_cls, spider)
