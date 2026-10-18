"""
纯网页爬虫：给定 URL，按明确字段或预设模式（links/body/table）抽取内容。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG_FILE = SCRIPT_DIR / 'crawl.txt'

PRESET_MODES: dict[str, list[str]] = {
    'links': ['链接'],
    'body': ['正文'],
    'table': ['表格'],
}

JOINQQ_BASE = 'https://join.qq.com'
JOINQQ_DETAIL_API = f'{JOINQQ_BASE}/api/v1/jobDetails/getJobDetailsByPostId'

DEFAULT_HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/120.0.0.0 Safari/537.36'
    ),
}

DOUBAN_HEADERS = {
    **DEFAULT_HEADERS,
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9',
    'Referer': 'https://movie.douban.com/',
}

JOINQQ_HEADERS = {
    **DEFAULT_HEADERS,
    'Accept': 'application/json, text/plain, */*',
    'Referer': f'{JOINQQ_BASE}/post.html',
    'Origin': JOINQQ_BASE,
}

JOINQQ_POST_RE = re.compile(
    r'^https?://(?:[\w.-]+\.)?join\.qq\.com/post_detail\.html',
    re.I,
)

# 字段别名 -> 索引里优先尝试的键（顺序）
FIELD_ALIAS_KEYS: dict[str, list[str]] = {
    '标题': ['标题', '题目'],
    '题目': ['题目', '标题'],
    '名称': ['名称', '电影名称', '片名', '名字'],
    '名字': ['名字', '名称', '电影名称', '片名'],
    '片名': ['片名', '电影名称', '名称'],
    '电影名称': ['电影名称', '名称', '片名'],
    '评分': ['评分', '分数', '电影评分'],
    '分数': ['分数', '评分', '电影评分'],
    '电影评分': ['电影评分', '评分', '分数'],
    '简介': ['简介', '摘要', '介绍'],
    '摘要': ['摘要', '简介', '介绍'],
    '介绍': ['介绍', '简介', '摘要'],
    '正文': ['正文', '内容', '文章'],
    '内容': ['内容', '正文', '文章'],
    '文章': ['文章', '正文', '内容'],
    '链接': ['链接', '网址列表'],
    '网址列表': ['网址列表', '链接'],
    '表格': ['表格'],
    '岗位名称': ['岗位名称', '名称', '标题'],
    '招聘项目': ['招聘项目'],
    '工作城市': ['工作城市'],
    '面试城市': ['面试城市'],
    '可选部门': ['可选部门'],
    '岗位职责': ['岗位职责'],
    '岗位要求': ['岗位要求'],
}


@dataclass
class CrawlOutcome:
    url: str
    ok: bool
    fields: list[str] = field(default_factory=list)
    data: dict[str, Any] | None = None
    missing: list[str] = field(default_factory=list)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            'url': self.url,
            'ok': self.ok,
            'fields': self.fields,
        }
        if self.ok:
            out['data'] = self.data
            if self.missing:
                out['missing'] = self.missing
        else:
            out['error'] = self.error
        return out


def text_of(element) -> str | None:
    if element is None:
        return None
    return element.get_text(strip=True)


def normalize_city_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]
    if isinstance(value, str):
        return [p for p in value.split() if p.strip()]
    return [str(value).strip()] if str(value).strip() else []


def joinqq_post_id(url: str) -> str | None:
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    for key in ('postid', 'postId'):
        if key in qs and qs[key]:
            return qs[key][0]
    m = re.search(r'/post[_-]?detail.*?/(\d+)', parsed.path, re.I)
    if m:
        return m.group(1)
    return None


def department_names(detail: dict) -> list[str]:
    names: list[str] = []
    for bg in detail.get('intentionBGDList') or []:
        for dept in bg.get('departmentList') or []:
            name = dept.get('name')
            if name:
                names.append(name)
    return names


def split_field_names(text: str) -> list[str]:
    parts = re.split(r'[、,，;；\s]+', text.strip())
    return [p for p in parts if p]


def dedupe_fields(names: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for name in names:
        if name not in seen:
            seen.add(name)
            ordered.append(name)
    return ordered


def fields_from_modes(modes: list[str]) -> list[str]:
    fields: list[str] = []
    for mode in modes:
        key = mode.strip().lower()
        preset = PRESET_MODES.get(key)
        if not preset:
            raise ValueError(
                f'未知模式「{mode}」，可选：{", ".join(PRESET_MODES)}'
            )
        fields.extend(preset)
    return dedupe_fields(fields)


def resolve_fields(
    modes: list[str] | None,
    field_args: list[str] | None,
    fields_csv: str | None,
) -> list[str]:
    names: list[str] = []
    if modes:
        names.extend(fields_from_modes(modes))
    if fields_csv:
        names.extend(split_field_names(fields_csv))
    for item in field_args or []:
        names.extend(split_field_names(item))
    names = dedupe_fields(names)
    if not names:
        raise ValueError(
            '请用 --mode（links/body/table）或 --field / --fields 指定要抽取的内容'
        )
    return names


def validate_url(url: str) -> str:
    url = url.strip()
    if not url.lower().startswith(('http://', 'https://')):
        raise ValueError('网址必须以 http:// 或 https:// 开头')
    return url


def scan_label_values(soup: BeautifulSoup) -> dict[str, str]:
    labels: dict[str, str] = {}
    for tag in soup.find_all(['dt', 'th', 'label', 'span', 'strong', 'b']):
        key = text_of(tag)
        if not key or len(key) > 30:
            continue
        key = key.rstrip(':：')
        if not key or key in labels:
            continue
        sib = tag.find_next_sibling()
        if sib is not None:
            val = text_of(sib)
            if val:
                labels[key] = val
                continue
        parent = tag.parent
        if parent:
            full = text_of(parent)
            if full and full.startswith(key):
                rest = full[len(key) :].lstrip(':：').strip()
                if rest:
                    labels[key] = rest
    return labels


def collect_links(soup: BeautifulSoup, base_url: str) -> list[str]:
    links: list[str] = []
    seen: set[str] = set()
    for a in soup.find_all('a', href=True):
        href = a['href'].strip()
        if not href or href.startswith(('#', 'javascript:')):
            continue
        abs_url = urljoin(base_url, href)
        if abs_url in seen:
            continue
        seen.add(abs_url)
        links.append(abs_url)
        if len(links) >= 200:
            break
    return links


def collect_tables(soup: BeautifulSoup) -> list[list[list[str]]]:
    tables: list[list[list[str]]] = []
    for table in soup.find_all('table'):
        rows: list[list[str]] = []
        for tr in table.find_all('tr'):
            cells = [text_of(td) or '' for td in tr.find_all(['td', 'th'])]
            if any(cells):
                rows.append(cells)
        if rows:
            tables.append(rows)
    return tables


def build_html_index(html: bytes, page_url: str) -> dict[str, Any]:
    if 'sec.douban.com' in page_url:
        raise RuntimeError(
            '请求被豆瓣拦截，请确认能在浏览器正常打开该链接，或稍后重试。'
        )
    soup = BeautifulSoup(html, 'lxml')
    labels = scan_label_values(soup)

    title = None
    if soup.title and soup.title.string:
        title = soup.title.string.strip()
    if not title:
        og_title = soup.find('meta', property='og:title')
        if og_title and og_title.get('content'):
            title = og_title['content'].strip()
    h1 = soup.find('h1')
    h1_text = text_of(h1)

    name_el = soup.find(attrs={'property': 'v:itemreviewed'})
    if name_el is None:
        name_el = soup.find(attrs={'itemprop': 'name'})
    name = text_of(name_el) or h1_text or title

    rating_el = soup.find(attrs={'property': 'v:average'})
    if rating_el is None:
        rating_el = soup.find(attrs={'itemprop': 'ratingValue'})
    if rating_el is None:
        rating_el = soup.find('strong', class_='rating_num')
    rating = text_of(rating_el)

    summary_el = soup.find(attrs={'property': 'v:summary'})
    if summary_el is None:
        summary_el = soup.find('span', class_='all hidden')
    if summary_el is None:
        summary_el = soup.find('meta', attrs={'name': 'description'})
        summary = summary_el.get('content', '').strip() if summary_el else None
    else:
        summary = text_of(summary_el)
    if not summary:
        og_desc = soup.find('meta', property='og:description')
        if og_desc and og_desc.get('content'):
            summary = og_desc['content'].strip()

    for tag in soup(['script', 'style', 'noscript']):
        tag.decompose()
    body = soup.find('body')
    body_text = text_of(body) if body else soup.get_text(separator='\n', strip=True)
    if body_text:
        body_text = re.sub(r'\n{3,}', '\n\n', body_text)

    links = collect_links(soup, page_url)
    tables = collect_tables(soup)

    index: dict[str, Any] = {
        '标题': title or h1_text,
        '题目': title or h1_text,
        '名称': name,
        '电影名称': name,
        '片名': name,
        '名字': name,
        '评分': rating,
        '分数': rating,
        '电影评分': rating,
        '简介': summary,
        '摘要': summary,
        '介绍': summary,
        '正文': body_text,
        '内容': body_text,
        '文章': body_text,
        '链接': links,
        '网址列表': links,
        '表格': tables,
        '_labels': labels,
    }
    index.update(labels)
    return index


def joinqq_index_from_api(detail: dict) -> dict[str, Any]:
    return {
        '岗位名称': detail.get('title'),
        '招聘项目': detail.get('projectName'),
        '工作城市': normalize_city_list(
            detail.get('workCityList') or detail.get('workCity')
        ),
        '面试城市': normalize_city_list(
            detail.get('recruitCityList') or detail.get('recruitCity')
        ),
        '可选部门': department_names(detail),
        '岗位职责': detail.get('desc'),
        '岗位要求': detail.get('request'),
        '标题': detail.get('title'),
        '名称': detail.get('title'),
    }


def fetch_joinqq_index(
    url: str,
    get: Callable[..., requests.Response],
) -> dict[str, Any]:
    post_id = joinqq_post_id(url)
    if not post_id:
        raise RuntimeError('无法从 URL 解析 postId')
    resp = get(
        JOINQQ_DETAIL_API,
        headers=JOINQQ_HEADERS,
        params={'postId': post_id},
        timeout=20,
    )
    resp.raise_for_status()
    body = resp.json()
    if body.get('status') != 0:
        raise RuntimeError(
            f'获取岗位详情失败：{body.get("message") or "未知错误"}'
        )
    detail = body.get('data')
    if not detail:
        raise RuntimeError('岗位详情为空')
    return joinqq_index_from_api(detail)


def value_present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict, tuple)):
        return len(value) > 0
    return True


def lookup_field(index: dict[str, Any], field_name: str) -> Any | None:
    if field_name in index and field_name != '_labels':
        val = index[field_name]
        if value_present(val):
            return val
    keys = FIELD_ALIAS_KEYS.get(field_name, [field_name])
    for key in keys:
        if key in index and key != '_labels':
            val = index[key]
            if value_present(val):
                return val
    labels = index.get('_labels') or {}
    if field_name in labels and value_present(labels[field_name]):
        return labels[field_name]
    return None


def pick_fields(
    index: dict[str, Any], field_names: list[str]
) -> tuple[dict[str, Any], list[str]]:
    data: dict[str, Any] = {}
    missing: list[str] = []
    for name in field_names:
        val = lookup_field(index, name)
        if val is None:
            missing.append(name)
            continue
        if name in ('链接', '网址列表') and isinstance(val, list):
            data[name] = val
        else:
            data[name] = val
    return data, missing


def should_use_joinqq_api(url: str, html: bytes) -> bool:
    if not JOINQQ_POST_RE.match(url):
        return False
    text = BeautifulSoup(html, 'lxml').get_text(strip=True)
    return len(text) < 400


def fetch_page(
    url: str,
    session: requests.Session | None = None,
    get: Callable[..., requests.Response] | None = None,
) -> requests.Response:
    is_douban = 'douban.com' in url.lower()
    sess = session
    if sess is None and is_douban:
        sess = requests.Session()
        sess.headers.update(DOUBAN_HEADERS)
        sess.get('https://movie.douban.com/', timeout=15)
    client = sess or requests
    request_get = get or client.get
    headers = DEFAULT_HEADERS if not is_douban else None
    return request_get(
        url,
        headers=headers,
        timeout=20,
        allow_redirects=True,
    )


def crawl_url(
    url: str,
    fields: list[str],
    session: requests.Session | None = None,
    get: Callable[..., requests.Response] | None = None,
) -> CrawlOutcome:
    try:
        url = validate_url(url)
    except ValueError as exc:
        return CrawlOutcome(url=url, ok=False, fields=fields, error=str(exc))

    try:
        resp = fetch_page(url, session=session, get=get)
        resp.raise_for_status()
        content_type = (resp.headers.get('Content-Type') or '').lower()

        if 'application/json' in content_type or (
            resp.text and resp.text.lstrip().startswith(('{', '['))
        ):
            try:
                payload = resp.json()
            except json.JSONDecodeError:
                payload = {'raw': resp.text}
            index: dict[str, Any] = {'正文': json.dumps(payload, ensure_ascii=False)}
            if isinstance(payload, dict):
                for k, v in payload.items():
                    if isinstance(v, (str, int, float, bool)):
                        index[str(k)] = v
        else:
            html = resp.content
            if should_use_joinqq_api(url, html):
                index = fetch_joinqq_index(url, get=get or (session or requests).get)
            else:
                index = build_html_index(html, resp.url)
                if JOINQQ_POST_RE.match(url):
                    try:
                        api_index = fetch_joinqq_index(
                            url, get=get or (session or requests).get
                        )
                        for k, v in api_index.items():
                            if value_present(v):
                                index[k] = v
                    except Exception:
                        pass

        data, missing = pick_fields(index, fields)
        if not data:
            return CrawlOutcome(
                url=url,
                ok=False,
                fields=fields,
                error=f'未能从页面解析：{", ".join(missing)}',
            )
        return CrawlOutcome(
            url=url,
            ok=True,
            fields=fields,
            data=data,
            missing=missing,
        )
    except Exception as exc:
        return CrawlOutcome(
            url=url,
            ok=False,
            fields=fields,
            error=str(exc),
        )


def format_outcome(outcome: CrawlOutcome, index: int) -> str:
    lines = [
        f'\n{"=" * 60}',
        f'[{index}] 网址：{outcome.url or "（无）"}',
    ]
    if not outcome.ok:
        lines.append(f'失败：{outcome.error}')
        return '\n'.join(lines)
    lines.append(f'已抽取：{", ".join(outcome.fields)}')
    if outcome.missing:
        lines.append(f'未找到：{", ".join(outcome.missing)}')
    data = outcome.data or {}
    for key in outcome.fields:
        if key not in data:
            continue
        val = data[key]
        if key in ('链接', '网址列表') and isinstance(val, list):
            shown = val[:20]
            lines.append(f'\n{key}（共 {len(val)} 条，展示 {len(shown)} 条）：')
            lines.append(' '.join(shown))
        elif key == '表格' and isinstance(val, list):
            lines.append(f'\n{key}：{len(val)} 个表格')
        else:
            text = str(val)
            if len(text) > 2000:
                text = text[:2000] + '\n…（已截断）'
            lines.append(f'\n{key}：')
            lines.append(text)
    return '\n'.join(lines)


@dataclass
class CrawlRequest:
    url: str
    modes: list[str]
    field_args: list[str]
    fields_csv: str | None


def load_config_file(path: Path) -> CrawlRequest | None:
    if not path.is_file():
        return None
    url = ''
    modes: list[str] = []
    field_parts: list[str] = []
    for line in path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if line.lower().startswith('url='):
            url = line.split('=', 1)[1].strip()
        elif line.lower().startswith('mode='):
            modes.extend(split_field_names(line.split('=', 1)[1]))
        elif line.lower().startswith('fields='):
            field_parts.append(line.split('=', 1)[1].strip())
    if not url:
        return None
    fields_csv = ','.join(field_parts) if field_parts else None
    return CrawlRequest(url=url, modes=modes, field_args=[], fields_csv=fields_csv)


def resolve_request(
    cli_url: str | None,
    modes: list[str],
    field_args: list[str],
    fields_csv: str | None,
) -> CrawlRequest:
    if cli_url:
        return CrawlRequest(
            url=cli_url,
            modes=modes,
            field_args=field_args,
            fields_csv=fields_csv,
        )
    for path in (DEFAULT_CONFIG_FILE, Path.cwd() / 'crawl.txt'):
        cfg = load_config_file(path)
        if cfg:
            if modes:
                cfg.modes = modes
            if field_args:
                cfg.field_args = field_args
            if fields_csv:
                cfg.fields_csv = fields_csv
            return cfg
    raise ValueError(
        f'请传入 URL，或在 {DEFAULT_CONFIG_FILE.name} 中配置 url= 与 mode=/fields='
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description='纯爬虫：URL + 字段名，或预设模式 links / body / table',
        epilog=(
            '示例：\n'
            '  python crawl.py https://example.com --mode links\n'
            '  python crawl.py https://example.com -f 标题 -f 评分\n'
            '  python crawl.py --fields 岗位名称,岗位职责 （无 URL 时读 crawl.txt）\n'
            f'无参数时读取 {DEFAULT_CONFIG_FILE.name}（url=、mode= 或 fields=）。'
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        'url',
        nargs='?',
        metavar='URL',
        help='要爬取的 http(s) 地址',
    )
    parser.add_argument(
        '-m',
        '--mode',
        action='append',
        choices=list(PRESET_MODES),
        metavar='MODE',
        help='预设：links=链接，body=正文，table=表格（可多次指定）',
    )
    parser.add_argument(
        '-f',
        '--field',
        action='append',
        metavar='NAME',
        help='要抽取的字段名（可多次指定）',
    )
    parser.add_argument(
        '--fields',
        metavar='NAMES',
        help='逗号分隔的字段名，如：标题,评分,简介',
    )
    parser.add_argument(
        '-o',
        '--output',
        metavar='FILE',
        help='将结果写入 JSON 文件',
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        req = resolve_request(args.url, args.mode or [], args.field or [], args.fields)
        field_list = resolve_fields(req.modes, req.field_args, req.fields_csv)
        url = validate_url(req.url)
    except ValueError as exc:
        build_parser().error(str(exc))

    outcomes = [crawl_url(url, field_list)]
    results = [o.to_dict() for o in outcomes]

    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f'已写入 {args.output}')

    for i, outcome in enumerate(outcomes, 1):
        print(format_outcome(outcome, i))

    if not outcomes[0].ok:
        print('\n完成：失败')
        return 1
    miss = outcomes[0].missing
    if miss:
        print(f'\n完成：成功（部分字段未找到：{", ".join(miss)}）')
    else:
        print('\n完成：成功')
    return 0


if __name__ == '__main__':
    sys.exit(main())
