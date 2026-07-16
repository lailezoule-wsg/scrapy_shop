from itemloaders import ItemLoader
from itemloaders.processors import TakeFirst, MapCompose, Join
from datetime import datetime
import pytz
from shop.utils.common import safe_strip

class BaseLoader(ItemLoader):
    
    # 输入处理器：每个字段值都会先经过 MapCompose 处理
    default_input_processor = MapCompose(safe_strip)  # 去除首尾空格
    
    # 输出处理器：取第一个值（适用于单值字段）
    default_output_processor = TakeFirst()
    # 创建时间和更新时间：自动填充当前时间
    created_at_in = MapCompose(
        lambda x: x or datetime.now(pytz.timezone('Asia/Shanghai'))
    )
    updated_at_in = MapCompose(
        lambda x: x or datetime.now(pytz.timezone('Asia/Shanghai'))
    )

