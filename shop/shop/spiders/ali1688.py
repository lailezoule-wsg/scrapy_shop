import scrapy
import re

from shop.loaders.DangDangLoaders import BookLoader
from shop.items.DangDangItem import BooksItem

from shop.utils.common import parse_date,_dd_is_valid_url

class ALi1688Spider(scrapy.Spider):
    name = "ali1688"
    allowed_domains = [
        # "1688.com",
    ]
    start_urls = [
        "http://bang.dangdang.com/books/ebooks/98.01.00.00.00.00-24hours-0-0-1-1"
    ]

    async def start(self):
        self.logger.warning(f"=" * 20 + "爬虫正式开始" + f"=" * 20)
        for url in self.start_urls:
            yield scrapy.Request(
                url = url,
                callback= self.parse,
            )

    async def parse(self, response):
        
        li_list = response.css("ul.bang_list_mode > li")
        self.logger.warning(f'*' * 10 +f'获取爬虫数量：{len(li_list)}' + f'*' * 10)

        for index, li in enumerate(li_list, 1):
            loader = BookLoader(item=BooksItem(), selector=li)
            loader.add_css("title","div.name > a::text")
            url = li.css("div.name > a::attr(href)").get()
            loader.add_value("url",url)
            loader.add_css("cover_image","div.pic > a > img::attr(src)")
            loader.add_css("price","div.price > p > span.price_n::text")
            pattern = r'\/(\d+)\.html'
            match = re.search(pattern,url)
            product_id = match.group(1) if match else 0
            loader.add_value("product_id",product_id)
            
            item = loader.load_item()
            if url:
                if not _dd_is_valid_url(url):
                    self.logger.warning(f"🚄🚄  无效的{url}请求")
                    continue
                yield response.follow(
                    url = url,
                    callback=self.parse_detail,
                    meta={
                        'item': item,
                        # 启用 Playwright
                        'playwright': True,  
                        'retry_count': 0,  # ✅ 重试计数
                        'max_retries': 3,  # ✅ 最大重试次数
                        # 可选，用于高级控制 当前不需要,加的话因为parse_detail没有关闭，
                        # 浏览器连接池已被耗尽，所有协程都在等待释放资源，导致协程阻塞
                        'playwright_include_page': True,  
                    },
                    headers={
                        'Referer': response.url  # ✅ 当前页面作为 Referer
                    },
                )
            # ✅ 调试：确认 yield 执行了
            self.logger.warning(f"✅ 已生成第 {index} 个详情页{url}请求")
        
        # 获取下一页
        next_page_num_str = response.css("ul.paging > li.next > a::attr(href)").get()
        if next_page_num_str:
            match = re.search(r"loadData\(\'(\d+)\'\)",next_page_num_str.strip())
            if match:
                next_page_num = match.group(1)
                next_page = re.sub(r'-\d+$',  f'-{next_page_num}', response.url)
                self.logger.warning(f"✅ ✅ 下个列表页::::{next_page}")
                if next_page:
                    yield response.follow(
                        url = next_page,
                        callback=self.parse,
                        headers={
                            'Referer': response.url  # ✅ 当前页面作为 Referer
                        },
                    )


    async def parse_detail(self,response):
        page = None
        retry_count = response.meta.get('retry_count', 0)
        max_retries = response.meta.get('max_retries', 3)
        try:
            page = response.meta.get('playwright_page')
            item = response.meta["item"]
            self.logger.warning(f'✅ 开始解析详情页{response.url} ;  书名：{item.get("title","")}')
            if page:
                await page.wait_for_load_state('networkidle', timeout=15000)
                await page.wait_for_load_state('domcontentloaded', timeout=15000)
                author = (
                    response.css("p#author > span > a::text").get() or
                    response.css('[dd_name="作者"] span a::text').get() or
                    response.xpath('//p[contains(text(), "作者：")]/span/a/text()').get() or
                    response.xpath('//span[contains(text(), "作者")]/following-sibling::a/text()').get()
                )
                item["author"] = author.strip() if author else ""
                self.logger.warning(f'作者元素: {item["author"]}')

                publisher = (
                    response.css("p#publisher > span > a::text").get() or
                    response.css('[dd_name="出版社"] span a::text').get() or
                    response.xpath('//p[contains(text(), "出版社：")]/span/a/text()').get()
                )
                item["publisher"] = publisher.strip() if publisher else ""
                self.logger.warning(f'出版社元素: {item["publisher"]}')

                # ✅ 多种方式获取出版时间
                published_at = (
                    response.xpath('//p[contains(text(), "出版时间：")]/text()').get() or
                    response.xpath('//span[contains(text(), "出版时间")]/following-sibling::text()').get() or
                    response.css('.publish-time::text').get()
                )
                if published_at:
                    item["published_at"] = parse_date(published_at.replace('出版时间：', '').strip())
                    self.logger.warning(f'出版时间元素: {item["published_at"]}')

                description = (
                    response.css('div#newEditModule *::text').getall() or
                    response.xpath('//div[@id="newEditModule"]//text()').getall()
                )
                if description:
                    description = ' '.join(description).strip()
                    description = ' '.join(description.split())
                    description = description.replace('&lt;br/&gt;', '\n')
                    item["description"] = description
                    self.logger.warning(f'简介元素: {item["description"]}')

                # 重试检测
                if self._has_required_data(item):
                    self.logger.warning(f'✅ 解析成功: {item.get("title")}')
                    yield item
                else:
                    # ❌ 数据不完整，需要重试
                    missing_fields = self._get_missing_fields(item)
                    self.logger.warning(f'⚠️ 数据不完整 (尝试 {retry_count + 1}/{max_retries}): {missing_fields}')
                    
                    if retry_count < max_retries - 1:
                        # 🔄 重试
                        self.logger.warning(f'🔄 重试第 {retry_count + 1} 次: {response.url}')
                        yield response.follow(
                            url=response.url,
                            callback=self.parse_detail,
                            meta={
                                'item': item,
                                'playwright': True,
                                'retry_count': retry_count + 1,
                                'max_retries': max_retries,
                            },
                            headers={'Referer': response.url},
                            dont_filter=True,
                        )
                    else:
                        # ❌ 重试次数用尽，返回已有数据
                        self.logger.warning(f'❌ 重试 {max_retries} 次失败: {response.url}')
                        yield item
        
        except Exception as e:
            self.logger.warning(f"🚄 详情页解析失败: {e}")
            import traceback
            traceback.print_exc()
            
            # ✅ 异常时也尝试重试
            if retry_count < max_retries - 1:
                self.logger.warning(f'🔄 异常重试 {retry_count + 1}/{max_retries}: {response.url}')
                if 'item' in response.meta:
                    yield scrapy.Request(
                        url=response.url,
                        callback=self.parse_detail,
                        meta={
                            'item': response.meta['item'],
                            'playwright': True,
                            'retry_count': retry_count + 1,
                            'max_retries': max_retries,
                        },
                        headers={'Referer': response.url},
                        dont_filter=True,
                    )
                else:
                    yield BooksItem()
            else:
                if 'item' in response.meta:
                    yield response.meta['item']
                else:
                    yield BooksItem()
        finally:
            if page:
                try:
                    await page.close()
                    self.logger.warning("✅ 页面已关闭")
                except Exception as e:
                    self.logger.warning(f"关闭页面失败: {e}")

    def _has_required_data(self, item):
        """检查是否有必要的数据"""
        # ✅ 至少要有作者或出版社（核心数据）
        return item.get('description') or item.get('author')

    def _get_missing_fields(self, item):
        """获取缺失的字段"""
        required_fields = ['author', 'publisher', 'published_at']
        missing = [f for f in required_fields if not item.get(f)]
        return missing if missing else '无'