# Define here the models for your scraped items
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html

import scrapy
from shop.items.BaseItem import BaseItem

class BooksItem(BaseItem):
    # define the fields for your item here like:
    # name = scrapy.Field()
    product_id = scrapy.Field()
    title = scrapy.Field()
    url = scrapy.Field()
    author = scrapy.Field()
    cover_image = scrapy.Field()
    cover_image_local = scrapy.Field()
    price = scrapy.Field()
    publisher = scrapy.Field()
    description = scrapy.Field()
    published_at = scrapy.Field()
    created_at = scrapy.Field()
    updated_at = scrapy.Field()
