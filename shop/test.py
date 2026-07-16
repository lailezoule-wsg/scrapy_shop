import re

from urllib.parse import urlparse

str = "javascript:loadData('2');"

pattern = r"loadData\(\'(\d+)\'\)"

# match = re.search(pattern,str)
# if match:
#     print(match.group(1))


url = "http://product.dangdang.com/1901371253.html"

print(urlparse(url))

pattern = r'\/(\d+)\.html'

match = re.search(pattern,url)
if match:
    print(match.group(1))