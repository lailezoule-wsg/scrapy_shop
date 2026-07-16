# loaders/book_loaders.py
from itemloaders import ItemLoader
from itemloaders.processors import TakeFirst, MapCompose, Join
from datetime import datetime
import pytz
import re
from shop.items.DangDangItem import BooksItem
from shop.loaders.BaseLoaders import BaseLoader
from shop.utils.common import parse_date,extract_price
    

class BookLoader(BaseLoader):
    default_item_class = BooksItem
    
    # 全局处理器
    # default_input_processor = MapCompose(str.strip)
    # default_output_processor = TakeFirst()
    
    # 标题：去掉多余空格
    title_in = MapCompose(str.strip, lambda x: re.sub(r'\s+', ' ', x))
    
    # URL：去除空格
    url_in = MapCompose(str.strip)
    
    # 作者：多个用逗号分隔
    author_in = MapCompose(str.strip)
    author_out = Join(', ')
    
    # 封面图
    cover_image_in = MapCompose(str.strip)
    cover_image_out = TakeFirst()
    
    # 封面图本地路径
    cover_image_local_in = MapCompose(str.strip)
    
    # 价格（修复）
    price_in = MapCompose(str.strip, extract_price)
    
    # 出版社
    publisher_in = MapCompose(str.strip)
    
    # 描述
    description_in = MapCompose(str.strip)
    description_out = Join('\n')
    
    # 发布时间（修复）
    published_at_in = MapCompose(str.strip, parse_date)