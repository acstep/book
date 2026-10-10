import http.server
import socketserver
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import json
import re
import os
import time
from concurrent.futures import ThreadPoolExecutor

PORT = 8080
DIRECTORY = os.path.dirname(os.path.abspath(__file__))

COMPANIES = {
    'NVIDIA': {'ticker': 'NVDA', 'color': '#76B900'},
    'INTEL': {'ticker': 'INTC', 'color': '#0071C5'},
    'MICROSOFT': {'ticker': 'MSFT', 'color': '#00A4EF'},
    'GOOGLE': {'ticker': 'GOOGL', 'color': '#EA4335'}
}

# 備援高畫質圖庫 (若該新聞網頁嚴格防爬蟲或無 og:image 時平滑遞補)
BACKUP_IMAGES = {
    'NVIDIA': [
        'https://images.unsplash.com/photo-1591488320449-011701bb6704?auto=format&fit=crop&w=1200&q=80',
        'https://images.unsplash.com/photo-1550751827-4bd374c3f58b?auto=format&fit=crop&w=1200&q=80',
        'https://images.unsplash.com/photo-1629654297299-c8506221ca97?auto=format&fit=crop&w=1200&q=80'
    ],
    'INTEL': [
        'https://images.unsplash.com/photo-1517077304055-6e89abbf09b0?auto=format&fit=crop&w=1200&q=80',
        'https://images.unsplash.com/photo-1581091226825-a6a2a5aee158?auto=format&fit=crop&w=1200&q=80',
        'https://images.unsplash.com/photo-1518770660439-4636190af475?auto=format&fit=crop&w=1200&q=80'
    ],
    'MICROSOFT': [
        'https://images.unsplash.com/photo-1526374965328-7f61d4dc18c5?auto=format&fit=crop&w=1200&q=80',
        'https://images.unsplash.com/photo-1451187580459-43490279c0fa?auto=format&fit=crop&w=1200&q=80',
        'https://images.unsplash.com/photo-1460925895917-afdab827c52f?auto=format&fit=crop&w=1200&q=80'
    ],
    'GOOGLE': [
        'https://images.unsplash.com/photo-1573804633927-bfcbcd909acd?auto=format&fit=crop&w=1200&q=80',
        'https://images.unsplash.com/photo-1519389950473-47ba0277781c?auto=format&fit=crop&w=1200&q=80',
        'https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?auto=format&fit=crop&w=1200&q=80'
    ]
}

# 記憶體快取以加快翻頁讀取速度
CACHE_DATA = {}
CACHE_TIME = 0
CACHE_TTL = 300  # 5分鐘

def extract_og_image(url):
    """直接連線新聞原始網頁，爬取該篇文章真實的 og:image 封面圖片"""
    if not url or not url.startswith('http'):
        return None
    try:
        req = urllib.request.Request(
            url,
            headers={
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
            }
        )
        with urllib.request.urlopen(req, timeout=3.5) as resp:
            # 只讀取 HTML 前 100KB (meta 標籤通常在最前段)
            chunk = resp.read(102400).decode('utf-8', errors='ignore')
            m = re.search(r'<meta[^>]+property=[\"\']og:image[\"\'][^>]+content=[\"\']([^\"\']+)[\"\']', chunk, re.I)
            if not m:
                m = re.search(r'<meta[^>]+content=[\"\']([^\"\']+)[\"\'][^>]+property=[\"\']og:image[\"\']', chunk, re.I)
            if not m:
                # 備選 twitter:image
                m = re.search(r'<meta[^>]+name=[\"\']twitter:image[\"\'][^>]+content=[\"\']([^\"\']+)[\"\']', chunk, re.I)
            
            if m:
                img_url = m.group(1).replace('&amp;', '&').strip()
                if img_url.startswith('//'):
                    img_url = 'https:' + img_url
                elif img_url.startswith('/'):
                    parsed = urllib.parse.urlparse(url)
                    img_url = f"{parsed.scheme}://{parsed.netloc}{img_url}"
                return img_url
    except Exception:
        pass
    return None

def process_single_item(item_data, company_key, idx):
    """並行處理個別新聞項目，提取真實 og:image"""
    link = item_data.get('link', '')
    real_img = extract_og_image(link)
    
    # 若抓到了原始真實網頁圖即使用，若無法獲取則使用精緻備援圖
    if real_img:
        item_data['image'] = real_img
        item_data['is_real_image'] = True
    else:
        b_list = BACKUP_IMAGES[company_key]
        item_data['image'] = b_list[idx % len(b_list)]
        item_data['is_real_image'] = False
    return item_data

def fetch_rss_news(force_refresh=False):
    global CACHE_DATA, CACHE_TIME
    now = time.time()
    if not force_refresh and CACHE_DATA and (now - CACHE_TIME < CACHE_TTL):
        return CACHE_DATA

    results = {}

    for key, info in COMPANIES.items():
        sym = info['ticker']
        # 使用帶有精確直鏈的財經 RSS 來源 (Yahoo Finance 官方 Headline 串流)
        url = f"https://finance.yahoo.com/rss/headline?s={sym}"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        items = []
        try:
            with urllib.request.urlopen(req, timeout=6) as resp:
                root = ET.fromstring(resp.read())
                raw_items = root.findall('.//item')[:10]
                
                prepared = []
                for item in raw_items:
                    title = item.find('title').text if item.find('title') is not None else '無標題'
                    link = item.find('link').text if item.find('link') is not None else '#'
                    pubDate = item.find('pubDate').text[:16] if item.find('pubDate') is not None and item.find('pubDate').text else ''
                    desc = item.find('description').text if item.find('description') is not None else ''
                    clean_desc = re.sub(r'<[^>]+>', '', desc).strip()
                    if not clean_desc:
                        clean_desc = f"{key} ({sym}) 最新市場動態與華爾街分析報告。"

                    source_name = 'Yahoo Finance'
                    parsed_domain = urllib.parse.urlparse(link).netloc
                    if parsed_domain:
                        source_name = parsed_domain.replace('www.', '').capitalize()

                    prepared.append({
                        'title': title,
                        'source': source_name,
                        'link': link,
                        'pubDate': pubDate,
                        'description': clean_desc,
                        'company': key,
                        'ticker': sym
                    })

                # 透過多執行緒快速並行爬取原始網頁 og:image
                with ThreadPoolExecutor(max_workers=6) as executor:
                    tasks = [executor.submit(process_single_item, p, key, i) for i, p in enumerate(prepared)]
                    items = [t.result() for t in tasks]

                results[key] = items
        except Exception as e:
            print(f"Error fetching {key}: {e}")
            results[key] = []

    CACHE_DATA = results
    CACHE_TIME = now
    return results

class FlipboardHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == '/api/news':
            params = urllib.parse.parse_qs(parsed.query)
            force = 'refresh' in params
            data = fetch_rss_news(force_refresh=force)
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))
        elif parsed.path == '/' or parsed.path == '':
            self.path = '/flipboard.html'
            return super().do_GET()
        else:
            return super().do_GET()

if __name__ == '__main__':
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", PORT), FlipboardHandler) as httpd:
        print(f"Server started at http://localhost:{PORT}")
        httpd.serve_forever()
