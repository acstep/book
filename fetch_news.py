import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import json
import re
import os
from concurrent.futures import ThreadPoolExecutor

HTTP_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml,application/rss+xml;q=0.9,*/*;q=0.8'
}

# ============================================================
# 20 大精選權威 AI 網站專屬來源清單 (100% 直連、無重導向、乾淨可翻譯)
# ============================================================
AI_FEEDS = [
    # 一、頂級 AI 實驗室與開源官方 Blog
    {'name': 'OpenAI', 'url': 'https://openai.com/news/rss.xml'},
    {'name': 'Google DeepMind', 'url': 'https://deepmind.google/blog/rss.xml'},
    {'name': 'Hugging Face', 'url': 'https://huggingface.co/blog/feed.xml'},
    {'name': 'Meta AI', 'url': 'https://engineering.fb.com/category/ai-research/feed/'},
    {'name': 'Microsoft Research', 'url': 'https://www.microsoft.com/en-us/research/feed/'},

    # 二、硬核技術拆解與 AI 工程師專屬 Blog / Newsletter
    {'name': 'Latent Space', 'url': 'https://www.latent.space/feed'},
    {'name': 'MarkTechPost', 'url': 'https://www.marktechpost.com/feed/'},
    {'name': 'Import AI', 'url': 'https://importai.substack.com/feed'},
    {'name': 'Simon Willison', 'url': 'https://simonwillison.net/atom/everything/'},

    # 三、AI 基準測試與算力硬體 Blog
    {'name': 'SemiAnalysis', 'url': 'https://www.semianalysis.com/feed'},
    {'name': "Tom's Hardware", 'url': 'https://www.tomshardware.com/feeds/all'},

    # 四、主流科技媒體之 AI 專題新聞版面
    {'name': 'VentureBeat AI', 'url': 'https://venturebeat.com/category/ai/feed/'},
    {'name': 'TechCrunch AI', 'url': 'https://techcrunch.com/category/artificial-intelligence/feed/'},
    {'name': 'MIT Tech Review', 'url': 'https://www.technologyreview.com/feed/'},
    {'name': 'Ars Technica AI', 'url': 'https://feeds.arstechnica.com/arstechnica/technology-lab'},
    {'name': 'The Verge AI', 'url': 'https://www.theverge.com/rss/index.xml'},
    {'name': 'Wired AI', 'url': 'https://www.wired.com/feed/tag/ai/latest/rss'}
]

FINANCE_FEEDS = [
    {'name': 'MarketWatch', 'url': 'https://feeds.content.dowjones.io/public/rss/mw_topstories'},
    {'name': 'MarketWatch Realtime', 'url': 'https://feeds.content.dowjones.io/public/rss/mw_realtimeheadlines'},
    {'name': 'BBC Business', 'url': 'https://feeds.bbci.co.uk/news/business/rss.xml'},
    {'name': 'NYTimes Business', 'url': 'https://rss.nytimes.com/services/xml/rss/nyt/Business.xml'},
    {'name': 'SemiAnalysis', 'url': 'https://www.semianalysis.com/feed'}
]

TECH_FEEDS = [
    {'name': 'TechCrunch', 'url': 'https://techcrunch.com/feed/'},
    {'name': 'BBC Tech', 'url': 'https://feeds.bbci.co.uk/news/technology/rss.xml'},
    {'name': 'NYTimes Tech', 'url': 'https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml'},
    {'name': 'Ars Technica', 'url': 'https://feeds.arstechnica.com/arstechnica/index'},
    {'name': "Tom's Hardware", 'url': 'https://www.tomshardware.com/feeds/all'},
    {'name': 'The Verge', 'url': 'https://www.theverge.com/rss/index.xml'},
    {'name': 'Wired', 'url': 'https://www.wired.com/feed/tag/ai/latest/rss'}
]

# 全新分類：股市 (Seeking Alpha 權威美股專欄)
STOCKS_FEEDS = [
    {'name': 'Seeking Alpha', 'url': 'https://seekingalpha.com/feed.xml'},
    {'name': 'Seeking Alpha Market Currents', 'url': 'https://seekingalpha.com/market_currents.xml'},
    {'name': 'Wall St Breakfast', 'url': 'https://seekingalpha.com/tag/wall-st-breakfast.xml'}
]

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
    ],
    'STOCKS': [
        'https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?auto=format&fit=crop&w=1200&q=80',
        'https://images.unsplash.com/photo-1590283603385-17ffb3a7f29f?auto=format&fit=crop&w=1200&q=80',
        'https://images.unsplash.com/photo-1642543492481-44e81e3914a7?auto=format&fit=crop&w=1200&q=80',
        'https://images.unsplash.com/photo-1535320903710-d993d3d77d29?auto=format&fit=crop&w=1200&q=80',
        'https://images.unsplash.com/photo-1526304640581-d334cdbbf45e?auto=format&fit=crop&w=1200&q=80'
    ]
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

def fetch_anthropic_news():
    """專屬抓取器：Anthropic 官方新聞與技術公告"""
    items = []
    try:
        url = 'https://www.anthropic.com/news'
        req = urllib.request.Request(url, headers=HTTP_HEADERS)
        with urllib.request.urlopen(req, timeout=5) as resp:
            html = resp.read().decode('utf-8', errors='ignore')
            matches = re.findall(r'href=[\"\'](/news/[^\"\']+)[\"\'][^>]*>(.*?)</a>', html, re.S)
            seen = set()
            for href, text in matches:
                full_link = f'https://www.anthropic.com{href}'
                if full_link in seen:
                    continue
                seen.add(full_link)
                clean_text = re.sub(r'<[^>]+>', ' ', text).strip()
                title = clean_text.split('\n')[0].strip() if clean_text else 'Anthropic News'
                # 排除純導覽或空字串
                if len(title) > 5 and 'view all' not in title.lower():
                    items.append({
                        'title': title,
                        'source': 'Anthropic News',
                        'link': full_link,
                        'pubDate': '最新發布',
                        'description': f'Anthropic 官方前沿技術與模型研究公告：{title}',
                        'category': 'AI'
                    })
    except Exception as e:
        print(f"Anthropic fetch error: {e}")
    return items

def fetch_artificial_analysis_articles():
    """專屬抓取器：Artificial Analysis 基準與評測文章"""
    items = []
    try:
        url = 'https://artificialanalysis.ai/articles'
        req = urllib.request.Request(url, headers=HTTP_HEADERS)
        with urllib.request.urlopen(req, timeout=5) as resp:
            html = resp.read().decode('utf-8', errors='ignore')
            slugs = set(re.findall(r'href=[\"\'](/articles/[^\"\'#?]+)[\"\']', html))
            for slug in slugs:
                clean_name = slug.replace('/articles/', '').replace('-', ' ').title()
                items.append({
                    'title': f'{clean_name} — AI Model Benchmark Analysis',
                    'source': 'Artificial Analysis',
                    'link': f'https://artificialanalysis.ai{slug}',
                    'pubDate': '基準報告',
                    'description': f'Artificial Analysis 權威模型實測數據分析，涵蓋 Token 輸出速度、延遲、吞吐量與性價比報告。',
                    'category': 'AI'
                })
    except Exception as e:
        print(f"Artificial Analysis fetch error: {e}")
    return items

def fetch_the_batch_issues():
    """專屬抓取器：The Batch (by DeepLearning.AI 吳恩達團隊)"""
    items = []
    try:
        url = 'https://www.deeplearning.ai/the-batch/'
        req = urllib.request.Request(url, headers=HTTP_HEADERS)
        with urllib.request.urlopen(req, timeout=5) as resp:
            html = resp.read().decode('utf-8', errors='ignore')
            issues = sorted(list(set(re.findall(r'href=[\"\'](/the-batch/issue-[0-9]+)[\"\']', html))), reverse=True)
            for issue_slug in issues[:5]:
                num = issue_slug.split('-')[-1]
                items.append({
                    'title': f'The Batch Issue #{num}: AI Weekly Insights & Engineering Trends',
                    'source': 'DeepLearning.AI The Batch',
                    'link': f'https://www.deeplearning.ai{issue_slug}/',
                    'pubDate': '週報精選',
                    'description': f'吳恩達團隊 The Batch 每週深度技術分析，探討前沿 AI 論文、商業落地與工程趨勢。',
                    'category': 'AI'
                })
    except Exception as e:
        print(f"The Batch fetch error: {e}")
    return items

def fetch_feed_items(feed_cfg, cat_key, seen_links):
    """解析標準 RSS 或 Atom 串流"""
    feed_items = []
    feed_url = feed_cfg['url']
    source_name = feed_cfg['name']

    try:
        req = urllib.request.Request(feed_url, headers=HTTP_HEADERS)
        with urllib.request.urlopen(req, timeout=5) as resp:
            content = resp.read()
            root = ET.fromstring(content)
            items = root.findall('.//item')
            if not items:
                items = root.findall('.//{http://www.w3.org/2005/Atom}entry')

            for item in items:
                link_node = item.find('link')
                if link_node is None:
                    continue
                link = link_node.text or link_node.get('href', '')
                link = link.strip() if link else ''

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
                    clean_desc = f"{source_name} 最新發布之專業報導與深度分析。"

                feed_items.append({
                    'title': title,
                    'source': source_name,
                    'link': link,
                    'pubDate': pubDate,
                    'description': clean_desc,
                    'category': cat_key
                })
    except Exception as e:
        print(f"Feed error [{source_name}] ({feed_url}): {e}")
    return feed_items

def run_fetch():
    out_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'news.json')

    # 載入既有乾淨歷史新聞 (排除 news.google.com)
    existing_data = {'AI': [], 'FINANCE': [], 'TECH': [], 'STOCKS': []}
    if os.path.exists(out_file):
        try:
            with open(out_file, 'r', encoding='utf-8') as f:
                loaded = json.load(f)
                for k in existing_data.keys():
                    if k in loaded and isinstance(loaded[k], list):
                        existing_data[k] = [
                            x for x in loaded[k]
                            if 'news.google.com' not in x.get('link', '')
                        ]
            print(f"Loaded existing clean history: AI={len(existing_data['AI'])}, FINANCE={len(existing_data['FINANCE'])}, TECH={len(existing_data['TECH'])}, STOCKS={len(existing_data['STOCKS'])}")
        except Exception as e:
            print(f"Failed to read existing news.json: {e}")

    results = {}
    print("\nStarting comprehensive fetching for AI, FINANCE, TECH...")

    # ==========================
    # 1. 抓取 AI 專題 (整合 20 大權威 AI 網站)
    # ==========================
    print("\nFetching category [AI] across 20 top authority sources...")
    ai_candidates = []
    seen_ai_links = set(x.get('link', '') for x in existing_data.get('AI', []))

    # (A) 抓取 Anthropic, Artificial Analysis, The Batch
    print("Fetching direct editorial sites (Anthropic, Artificial Analysis, The Batch)...")
    special_items = fetch_anthropic_news() + fetch_artificial_analysis_articles() + fetch_the_batch_issues()
    for s_item in special_items:
        if s_item['link'] not in seen_ai_links:
            seen_ai_links.add(s_item['link'])
            ai_candidates.append(s_item)

    # (B) 並行抓取所有 AI RSS 串流
    with ThreadPoolExecutor(max_workers=8) as executor:
        feed_tasks = [executor.submit(fetch_feed_items, f_cfg, 'AI', seen_ai_links) for f_cfg in AI_FEEDS]
        for t in feed_tasks:
            ai_candidates.extend(t.result())

    selected_ai = ai_candidates[:35]
    print(f"Found {len(ai_candidates)} new AI items, processing top {len(selected_ai)}...")
    new_ai_processed = []
    if selected_ai:
        with ThreadPoolExecutor(max_workers=8) as executor:
            tasks = [executor.submit(process_single_item, item, 'AI', i) for i, item in enumerate(selected_ai)]
            new_ai_processed = [t.result() for t in tasks]

    results['AI'] = (new_ai_processed + existing_data.get('AI', []))[:150]
    print(f"✓ [AI] 累積儲存 {len(results['AI'])} 篇 20 大權威直連新聞 (本次新增 {len(new_ai_processed)} 篇)。")

    # ==========================
    # 2. 抓取 全球財經 (FINANCE)
    # ==========================
    print("\nFetching category [FINANCE]...")
    finance_candidates = []
    seen_fin_links = set(x.get('link', '') for x in existing_data.get('FINANCE', []))

    with ThreadPoolExecutor(max_workers=6) as executor:
        fin_tasks = [executor.submit(fetch_feed_items, f_cfg, 'FINANCE', seen_fin_links) for f_cfg in FINANCE_FEEDS]
        for t in fin_tasks:
            finance_candidates.extend(t.result())

    selected_fin = finance_candidates[:25]
    print(f"Found {len(finance_candidates)} new FINANCE items, processing top {len(selected_fin)}...")
    new_fin_processed = []
    if selected_fin:
        with ThreadPoolExecutor(max_workers=8) as executor:
            tasks = [executor.submit(process_single_item, item, 'FINANCE', i) for i, item in enumerate(selected_fin)]
            new_fin_processed = [t.result() for t in tasks]

    results['FINANCE'] = (new_fin_processed + existing_data.get('FINANCE', []))[:150]
    print(f"✓ [FINANCE] 累積儲存 {len(results['FINANCE'])} 篇權威直連財經新聞。")

    # ==========================
    # 3. 抓取 科技趨勢 (TECH)
    # ==========================
    print("\nFetching category [TECH]...")
    tech_candidates = []
    seen_tech_links = set(x.get('link', '') for x in existing_data.get('TECH', []))

    with ThreadPoolExecutor(max_workers=6) as executor:
        tech_tasks = [executor.submit(fetch_feed_items, f_cfg, 'TECH', seen_tech_links) for f_cfg in TECH_FEEDS]
        for t in tech_tasks:
            tech_candidates.extend(t.result())

    selected_tech = tech_candidates[:25]
    print(f"Found {len(tech_candidates)} new TECH items, processing top {len(selected_tech)}...")
    new_tech_processed = []
    if selected_tech:
        with ThreadPoolExecutor(max_workers=8) as executor:
            tasks = [executor.submit(process_single_item, item, 'TECH', i) for i, item in enumerate(selected_tech)]
            new_tech_processed = [t.result() for t in tasks]

    results['TECH'] = (new_tech_processed + existing_data.get('TECH', []))[:150]
    print(f"✓ [TECH] 累積儲存 {len(results['TECH'])} 篇權威直連科技新聞。")

    # ==========================
    # 4. 抓取 股市 (STOCKS) - Seeking Alpha 三大權威美股專欄
    # ==========================
    print("\nFetching category [STOCKS] from Seeking Alpha feeds...")
    stocks_candidates = []
    seen_stocks_links = set(x.get('link', '') for x in existing_data.get('STOCKS', []))

    with ThreadPoolExecutor(max_workers=4) as executor:
        stocks_tasks = [executor.submit(fetch_feed_items, f_cfg, 'STOCKS', seen_stocks_links) for f_cfg in STOCKS_FEEDS]
        for t in stocks_tasks:
            stocks_candidates.extend(t.result())

    selected_stocks = stocks_candidates[:35]
    print(f"Found {len(stocks_candidates)} new STOCKS items, processing top {len(selected_stocks)}...")
    new_stocks_processed = []
    if selected_stocks:
        with ThreadPoolExecutor(max_workers=8) as executor:
            tasks = [executor.submit(process_single_item, item, 'STOCKS', i) for i, item in enumerate(selected_stocks)]
            new_stocks_processed = [t.result() for t in tasks]

    results['STOCKS'] = (new_stocks_processed + existing_data.get('STOCKS', []))[:150]
    print(f"✓ [STOCKS] 累積儲存 {len(results['STOCKS'])} 篇 Seeking Alpha 深度股市外電。")

    # 寫入更新 news.json
    with open(out_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n全部完成！已成功整合四大分類 (AI, 財經, 科技, 股市 Seeking Alpha)，海量資料庫寫入 {out_file}")

if __name__ == '__main__':
    run_fetch()
