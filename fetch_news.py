import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import json
import re
import os
from concurrent.futures import ThreadPoolExecutor

# 三大核心類別：全部採用 100% 原文直連、無重導向、乾淨可翻譯的權威媒體 RSS 源 (TechCrunch, MarketWatch, BBC, NYTimes, Yahoo)
CATEGORY_FEEDS = {
    'AI': {
        'name': '人工智慧 (AI)',
        'feeds': [
            'https://techcrunch.com/category/artificial-intelligence/feed/',
            'https://feeds.arstechnica.com/arstechnica/technology-lab',
            'https://www.theverge.com/rss/index.xml',
            'https://finance.yahoo.com/rss/headline?s=NVDA',
            'https://finance.yahoo.com/rss/headline?s=MSFT',
            'https://finance.yahoo.com/rss/headline?s=GOOGL',
            'https://finance.yahoo.com/rss/headline?s=AMD',
            'https://finance.yahoo.com/rss/headline?s=PLTR',
            'https://finance.yahoo.com/rss/headline?s=TSM'
        ],
        'default_tag': 'AI 尖端前沿'
    },
    'FINANCE': {
        'name': '全球財經 (Finance)',
        'feeds': [
            'https://feeds.content.dowjones.io/public/rss/mw_topstories',
            'https://feeds.content.dowjones.io/public/rss/mw_realtimeheadlines',
            'https://feeds.bbci.co.uk/news/business/rss.xml',
            'https://rss.nytimes.com/services/xml/rss/nyt/Business.xml',
            'https://finance.yahoo.com/rss/headline?s=SPY',
            'https://finance.yahoo.com/rss/headline?s=QQQ',
            'https://finance.yahoo.com/rss/headline?s=TSLA',
            'https://finance.yahoo.com/rss/headline?s=JPM',
            'https://finance.yahoo.com/rss/headline?s=AMZN',
            'https://finance.yahoo.com/rss/headline?s=BRK-B'
        ],
        'default_tag': '全球財經市場'
    },
    'TECH': {
        'name': '科技趨勢 (Tech)',
        'feeds': [
            'https://techcrunch.com/feed/',
            'https://feeds.bbci.co.uk/news/technology/rss.xml',
            'https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml',
            'https://feeds.arstechnica.com/arstechnica/index',
            'https://finance.yahoo.com/rss/headline?s=AAPL',
            'https://finance.yahoo.com/rss/headline?s=INTC',
            'https://finance.yahoo.com/rss/headline?s=META',
            'https://finance.yahoo.com/rss/headline?s=TSM',
            'https://finance.yahoo.com/rss/headline?s=QCOM',
            'https://finance.yahoo.com/rss/headline?s=ORCL'
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
        'https://images.unsplash.com/photo-1550751827-4bd374c3f58b?auto=format&fit=crop&w=1200&q=80',
        'https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?auto=format&fit=crop&w=1200&q=80'
    ],
    'FINANCE': [
        'https://images.unsplash.com/photo-1590283603385-17ffb3a7f29f?auto=format&fit=crop&w=1200&q=80',
        'https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?auto=format&fit=crop&w=1200&q=80',
        'https://images.unsplash.com/photo-1460925895917-afdab827c52f?auto=format&fit=crop&w=1200&q=80',
        'https://images.unsplash.com/photo-1526304640581-d334cdbbf45e?auto=format&fit=crop&w=1200&q=80',
        'https://images.unsplash.com/photo-1535320903710-d993d3d77d29?auto=format&fit=crop&w=1200&q=80'
    ],
    'TECH': [
        'https://images.unsplash.com/photo-1518770660439-4636190af475?auto=format&fit=crop&w=1200&q=80',
        'https://images.unsplash.com/photo-1517077304055-6e89abbf09b0?auto=format&fit=crop&w=1200&q=80',
        'https://images.unsplash.com/photo-1531297484001-80022131f5a1?auto=format&fit=crop&w=1200&q=80',
        'https://images.unsplash.com/photo-1550745165-9bc0b252726f?auto=format&fit=crop&w=1200&q=80',
        'https://images.unsplash.com/photo-1519389950473-47ba0277781c?auto=format&fit=crop&w=1200&q=80'
    ]
}

HTTP_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
}

def translate_to_zh(text):
    """將英文標題或摘要自動翻譯成繁體中文 (zh-TW)"""
    if not text or not text.strip():
        return text
    try:
        url = "https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl=zh-TW&dt=t&q=" + urllib.parse.quote(text)
        req = urllib.request.Request(url, headers=HTTP_HEADERS)
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
        req = urllib.request.Request(url, headers=HTTP_HEADERS)
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
    link = item_data.get('link', '')
    real_img = extract_og_image(link)
    if real_img:
        item_data['image'] = real_img
        item_data['is_real_image'] = True
    else:
        b_list = BACKUP_IMAGES[cat_key]
        item_data['image'] = b_list[idx % len(b_list)]
        item_data['is_real_image'] = False

    raw_title = item_data.get('title', '')
    raw_desc = item_data.get('description', '')
    item_data['title'] = translate_to_zh(raw_title)
    item_data['description'] = translate_to_zh(raw_desc)
    item_data['original_title'] = raw_title
    item_data['category'] = cat_key

    return item_data

def run_fetch():
    out_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'news.json')

    # 1. 載入既有歷史新聞，並【徹底過濾清除】所有導致重導向錯誤的 news.google.com 連結！
    existing_data = {'AI': [], 'FINANCE': [], 'TECH': []}
    if os.path.exists(out_file):
        try:
            with open(out_file, 'r', encoding='utf-8') as f:
                loaded = json.load(f)
                for k in existing_data.keys():
                    if k in loaded and isinstance(loaded[k], list):
                        # 只保留非 news.google.com 的直連乾淨新聞
                        clean_items = [
                            item for item in loaded[k]
                            if 'news.google.com' not in item.get('link', '')
                        ]
                        existing_data[k] = clean_items
            print(f"Loaded valid clean history: AI={len(existing_data['AI'])}, FINANCE={len(existing_data['FINANCE'])}, TECH={len(existing_data['TECH'])}")
        except Exception as e:
            print(f"Failed to read existing news.json: {e}")

    results = {}
    print("\nStarting clean direct-link fetching for AI, FINANCE, TECH...")

    for cat_key, cat_cfg in CATEGORY_FEEDS.items():
        print(f"\nFetching category [{cat_key}]...")
        raw_candidates = []
        seen_links = set(item.get('link', '') for item in existing_data.get(cat_key, []))

        for feed_url in cat_cfg['feeds']:
            try:
                req = urllib.request.Request(feed_url, headers=HTTP_HEADERS)
                with urllib.request.urlopen(req, timeout=5) as resp:
                    content = resp.read()
                    root = ET.fromstring(content)
                    items = root.findall('.//item')
                    if not items:
                        items = root.findall('.//{http://www.w3.org/2005/Atom}entry')

                    for item in items:
                        # 支援 RSS <link> 或 Atom <link href="...">
                        link_node = item.find('link')
                        if link_node is None:
                            continue
                        link = link_node.text or link_node.get('href', '')
                        link = link.strip() if link else ''

                        # 徹底排除無效的 news.google.com 重導向
                        if not link or 'news.google.com' in link or link in seen_links:
                            continue
                        seen_links.add(link)

                        title_node = item.find('title')
                        title = title_node.text.strip() if title_node is not None and title_node.text else '無標題'

                        pubDate_node = item.find('pubDate') or item.find('{http://www.w3.org/2005/Atom}published')
                        pubDate = pubDate_node.text[:16] if pubDate_node is not None and pubDate_node.text else ''

                        desc_node = item.find('description') or item.find('{http://www.w3.org/2005/Atom}summary')
                        desc = desc_node.text if desc_node is not None and desc_node.text else ''
                        clean_desc = re.sub(r'<[^>]+>', '', desc).strip()
                        if not clean_desc:
                            clean_desc = f"{cat_cfg['name']} 最新市場趨勢與深度分析報告。"

                        parsed_domain = urllib.parse.urlparse(link).netloc
                        source_name = parsed_domain.replace('www.', '').capitalize() if parsed_domain else '權威外電'

                        raw_candidates.append({
                            'title': title,
                            'source': source_name,
                            'link': link,
                            'pubDate': pubDate,
                            'description': clean_desc,
                            'category': cat_key
                        })
            except Exception as e:
                print(f"Feed error {feed_url}: {e}")

        selected_new = raw_candidates[:25]
        print(f"Found {len(raw_candidates)} clean items in [{cat_key}], processing top {len(selected_new)}...")

        newly_processed = []
        if selected_new:
            with ThreadPoolExecutor(max_workers=8) as executor:
                tasks = [executor.submit(process_single_item, item, cat_key, i) for i, item in enumerate(selected_new)]
                newly_processed = [t.result() for t in tasks]

        # 累積合併：新文章置頂，乾淨直連歷史文章接續在後
        combined = newly_processed + existing_data.get(cat_key, [])
        results[cat_key] = combined[:150]
        print(f"✓ [{cat_key}] 累積儲存 {len(results[cat_key])} 篇 100% 直連無障礙新聞。")

    with open(out_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n全部完成！100% 直連權威外電已寫入 {out_file}")

if __name__ == '__main__':
    run_fetch()
