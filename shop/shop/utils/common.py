import re
import os
import glob
from datetime import datetime,timedelta

def safe_strip(value):
    """安全去除首尾空格，支持字符串和数字"""
    if value is None:
        return ''
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        return value.strip()
    return value

def parse_date(value):
    """解析多种日期格式，返回 date 对象"""
    if not value:
        return None
    value = str(value).strip()
    
    date_formats = [
        '%Y-%m-%d',           # 2025-10-22
        '%Y/%m/%d',           # 2025/10/22
        '%Y年%m月%d日',       # 2025年10月22日
        '%Y-%m-%d %H:%M:%S',  # 2025-10-22 14:30:00
        '%Y/%m/%d %H:%M:%S',  # 2025/10/22 14:30:00
    ]
    
    for fmt in date_formats:
        try:
            dt = datetime.strptime(value, fmt)
            # ✅ 关键：返回 date 对象，不是 datetime
            return dt.date()
        except ValueError:
            continue
    
    # 如果都失败，返回 None
    return None

def extract_price(value):
    """提取价格中的数字"""
    if not value:
        return 0.0
    cleaned = re.sub(r'[¥￥$€,]', '', str(value))
    match = re.search(r'(\d+\.?\d*)', cleaned)
    return float(match.group(1)) if match else 0.0

def _dd_is_valid_url(url):
        """检查 URL 是否有效"""
        if not url:
            return False
        # 跳过 404 页面
        if '404' in url:
            return False
        if 'touch/ddreader50' in url:
            return False
        return True

# 清理多少天前日志
def clean_old_logs_by_day(log_dir='logs', days_to_keep=30):
    """清理指定天数前的日志文件"""
    cutoff = datetime.now() - timedelta(days=days_to_keep)
    if not os.path.exists(log_dir):
        return
    for filename in os.listdir(log_dir):
        filepath = os.path.join(log_dir, filename)
        if os.path.isfile(filepath):
            # 获取文件修改时间
            mtime = datetime.fromtimestamp(os.path.getmtime(filepath))
            if mtime < cutoff:
                try:
                    os.remove(filepath)
                    print(f"🗑️ 删除旧日志: {filename}")
                except Exception as e:
                    print(f"❌ 删除失败: {filename}, {e}")
# 保留最近多少个个日志文件
def clean_old_logs_by_count(log_dir='logs', keep_count=10):
    """
    清理旧日志文件，只保留最近 N 个文件
    Args:
        log_dir: 日志目录
        keep_count: 保留的文件数量
    """
    if not os.path.exists(log_dir):
        return
    # 获取所有日志文件（按修改时间排序）
    log_files = glob.glob(os.path.join(log_dir, '*.log'))
    if len(log_files) <= keep_count:
        print(f"📊 日志文件 {len(log_files)} 个，无需清理")
        return
    # 按修改时间排序（最新的在前）
    log_files.sort(key=os.path.getmtime, reverse=True)
    # 删除多余的文件（保留前 keep_count 个）
    files_to_delete = log_files[keep_count:]
    for filepath in files_to_delete:
        try:
            os.remove(filepath)
            print(f"🗑️ 删除旧日志: {os.path.basename(filepath)}")
        except Exception as e:
            print(f"❌ 删除失败: {filepath}, {e}")
    
    print(f"✅ 保留最近 {keep_count} 个日志文件")