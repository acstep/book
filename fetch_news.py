import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import json
import re
import os
from concurrent.futures import ThreadPoolExecutor

COMPANIES = {
    'NVIDIA': {'ticker': 'NVDA', 'color': '#76B900'},
    'INTEL': {'ticker': 'INTC', 'color': '#0071C5'},
    'MICROSOFT': {'ticker': 'MSFT', 'color': '#00A4EF'},
    'GOOGLE': {'ticker': 'GOOGL', 'color': '#EA4335'}
}

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

def extract_og_image(url):
    if not url or not url.startswith('http'):
        return None
    try:
        req = urllib.request.Request(
            url,
            headers={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'}
        )
        with urllib.request.urlopen(req, timeout=4) as resp:
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

def process_single_item(item_data, company_key, idx):
    link = item_data.get('link', '')
    real_img = extract_og_image(link)
    if real_img:
        item_data['image'] = real_img
        item_data['is_real_image'] = True
    else:
        b_list = BACKUP_IMAGES[company_key]
        item_data['image'] = b_list[idx % len(b_list)]
        item_data['is_real_image'] = False
    return item_data

def run_fetch():
    results = {}
    print("Starting fetching news for GitHub Pages...")
    for key, info in COMPANIES.items():
        sym = info['ticker']
        url = f"https://finance.yahoo.com/rss/headline?s={sym}"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        items = []
        try:
            with urllib.request.urlopen(req, timeout=8) as resp:
                root = ET.fromstring(resp.read())
                raw_items = root.findall('.//item')[:12]
                
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

                with ThreadPoolExecutor(max_workers=6) as executor:
                    tasks = [executor.submit(process_single_item, p, key, i) for i, p in enumerate(prepared)]
                    items = [t.result() for t in tasks]

                results[key] = items
                print(f"✓ {key}: {len(items)} articles processed.")
        except Exception as e:
            print(f"✗ Error fetching {key}: {e}")
            results[key] = []

    out_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'news.json')
    with open(out_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"Done! Saved news data to {out_file}")

if __name__ == '__main__':
    run_fetch()

