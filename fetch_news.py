import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import json
import re
import os
from concurrent.futures import ThreadPoolExecutor

# 三大核心類別與其對應的 RSS 串流組合 (保證每類別 25~35+ 篇以上海量文章)
CATEGORY_FEEDS = {
    'AI': {
        'name': '人工智慧 (AI)',
        'feeds': [
            'https://finance.yahoo.com/rss/headline?s=NVDA',
            'https://finance.yahoo.com/rss/headline?s=MSFT',
            'https://finance.yahoo.com/rss/headline?s=GOOGL',
            'https://finance.yahoo.com/rss/headline?s=AMD',
            'https://finance.yahoo.com/rss/headline?s=PLTR'
        ],
        'default_tag': 'AI 尖端前沿'
    },
    'FINANCE': {
        'name': '全球財經 (Finance)',
        'feeds': [
            'https://finance.yahoo.com/rss/headline?s=SPY',
            'https://finance.yahoo.com/rss/headline?s=QQQ',
            'https://finance.yahoo.com/rss/headline?s=TSLA',
            'https://finance.yahoo.com/rss/headline?s=JPM',
            'https://finance.yahoo.com/rss/headline?s=AMZN'
        ],
        'default_tag': '全球財經市場'
    },
    'TECH': {
        'name': '科技趨勢 (Tech)',
        'feeds': [
            'https://finance.yahoo.com/rss/headline?s=AAPL',
            'https://finance.yahoo.com/rss/headline?s=INTC',
            'https://finance.yahoo.com/rss/headline?s=META',
            'https://finance.yahoo.com/rss/headline?s=TSM',
            'https://finance.yahoo.com/rss/headline?s=QCOM'
        ],
        'default_tag': '科技創新動向'
    }
}

# 備援高畫質圖庫
BACKUP_IMAGES = {
    'AI': [
        'https://images.unsplash.com/photo-1620712943543-bcc4688e7485?auto=format&fit=crop&w=1200&q=80',
        'https://images.unsplash.com/photo-1591488320449-011701bb6704?auto=format&fit=crop&w=1200&q=80',
        'https://images.unsplash.com/photo-1677442136019-21780efad99a?auto=format&fit=crop&w=1200&q=80',
        'https://images.unsplash.com/photo-1550751827-4bd374c3f58b?auto=format&fit=crop&w=1200&q=80'
    ],
    'FINANCE': [
        'https://images.unsplash.com/photo-1590283603385-17ffb3a7f29f?auto=format&fit=crop&w=1200&q=80',
        'https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?auto=format&fit=crop&w=1200&q=80',
        'https://images.unsplash.com/photo-1460925895917-afdab827c52f?auto=format&fit=crop&w=1200&q=80',
        'https://images.unsplash.com/photo-1526304640581-d334cdbbf45e?auto=format&fit=crop&w=1200&q=80'
    ],
    'TECH': [
        'https://images.unsplash.com/photo-1518770660439-4636190af475?auto=format&fit=crop&w=1200&q=80',
        'https://images.unsplash.com/photo-1517077304055-6e89abbf09b0?auto=format&fit=crop&w=1200&q=80',
        'https://images.unsplash.com/photo-1531297484001-80022131f5a1?auto=format&fit=crop&w=1200&q=80',
        'https://images.unsplash.com/photo-1550745165-9bc0b252726f?auto=format&fit=crop&w=1200&q=80'
    ]
}

def translate_to_zh(text):
    """將英文標題或摘要自動翻譯成繁體中文 (zh-TW)"""
    if not text or not text.strip():
        return text
    try:
        url = "https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl=zh-TW&dt=t&q=" + urllib.parse.quote(text)
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=3.5) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            trans = ''.join([part[0] for part in data[0] if part and part[0]])
            return trans if trans else text
    except Exception:
        return text

def extract_og_image(url):
    """連線原始網頁爬取真實 og:image 圖片"""
    if not url or not url.startswith('http'):
        return None
    try:
        req = urllib.request.Request(
            url,
            headers={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'}
        )
        with urllib.request.urlopen(req, timeout=3.5) as resp:
            chunk = resp.read(102400).decode('utf-8', errors='ignore')
            m = re.search(r'<meta[^>]+property=[\"\']og:image[\"\'][^>]+content=[\"\']([^\"\']+)[\"\']', chunk, re.I)
            if not m:
                m = re.search(r'<meta[^>]+content=[\"\']([^\"\']+)[\"\'][^>]+property=[\"\']og:image[\"\']', chunk, re.I)
            if not m:
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

def process_single_item(item_data, cat_key, idx):
    # 1. 抓取原始真實封面圖
    link = item_data.get('link', '')
    real_img = extract_og_image(link)
    if real_img:
        item_data['image'] = real_img
        item_data['is_real_image'] = True
    else:
        b_list = BACKUP_IMAGES[cat_key]
        item_data['image'] = b_list[idx % len(b_list)]
        item_data['is_real_image'] = False

    # 2. 自動翻譯為繁體中文
    raw_title = item_data.get('title', '')
    raw_desc = item_data.get('description', '')
    item_data['title'] = translate_to_zh(raw_title)
    item_data['description'] = translate_to_zh(raw_desc)
    item_data['original_title'] = raw_title
    item_data['category'] = cat_key

    return item_data

def run_fetch():
    results = {}
    print("Starting massive fetching for categories: AI, FINANCE, TECH...")

    for cat_key, cat_cfg in CATEGORY_FEEDS.items():
        print(f"\nFetching category [{cat_key}]...")
        raw_candidates = []
        seen_links = set()

        for feed_url in cat_cfg['feeds']:
            try:
                req = urllib.request.Request(feed_url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=5) as resp:
                    root = ET.fromstring(resp.read())
                    items = root.findall('.//item')
                    for item in items:
                        link = item.find('link').text if item.find('link') is not None else ''
                        if not link or link in seen_links:
                            continue
                        seen_links.add(link)

                        title = item.find('title').text if item.find('title') is not None else '無標題'
                        pubDate = item.find('pubDate').text[:16] if item.find('pubDate') is not None and item.find('pubDate').text else ''
                        desc = item.find('description').text if item.find('description') is not None else ''
                        clean_desc = re.sub(r'<[^>]+>', '', desc).strip()
                        if not clean_desc:
                            clean_desc = f"{cat_cfg['name']} 最新市場趨勢與深度分析報告。"

                        parsed_domain = urllib.parse.urlparse(link).netloc
                        source_name = parsed_domain.replace('www.', '').capitalize() if parsed_domain else 'Yahoo Finance'

                        raw_candidates.append({
                            'title': title,
                            'source': source_name,
                            'link': link,
                            'pubDate': pubDate,
                            'description': clean_desc,
                            'category': cat_key
                        })
            except Exception as e:
                print(f"Error reading feed {feed_url}: {e}")

        # 每個類別精選 28 篇 (足夠翻 10~15 頁！)
        selected_candidates = raw_candidates[:28]
        print(f"Found {len(raw_candidates)} items in [{cat_key}], processing top {len(selected_candidates)}...")

        with ThreadPoolExecutor(max_workers=8) as executor:
            tasks = [executor.submit(process_single_item, item, cat_key, i) for i, item in enumerate(selected_candidates)]
            cat_articles = [t.result() for t in tasks]

        results[cat_key] = cat_articles
        print(f"✓ [{cat_key}] 完成 {len(cat_articles)} 篇深度新聞處理。")

    out_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'news.json')
    with open(out_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n全部完成！海量雜誌庫已寫入 {out_file}")

if __name__ == '__main__':
    run_fetch()
