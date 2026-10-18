# Web-Crawler

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776ab?style=flat-square&logo=python&logoColor=white)](#)
[![CLI](https://img.shields.io/badge/Interface-Command%20Line-555?style=flat-square)](#)
[![Config](https://img.shields.io/badge/Config-crawl.txt-2a4a6b?style=flat-square)](#)
[![Tests](https://img.shields.io/badge/Tests-unittest%20%28offline%29-0b6?style=flat-square)](#)

[English](#english) | [简体中文](#简体中文)

Repository: [github.com/Flin0498/Web-Crawler](https://github.com/Flin0498/Web-Crawler)

---

<h2 id="english">English</h2>

### 1. Abstract

This project is a **small, explicit web scraper** (not an LLM agent):

- You provide a **URL** and **what to extract**—field names or preset modes
- It fetches the page (or a matching public JSON API for empty HTML shells) and returns **only the requested fields**
- Missing extractors or HTTP errors are reported clearly; it does **not** dump the full page by default

**Preset modes**

| Mode | Extracts |
|------|----------|
| `links` | Hyperlinks (`链接`) |
| `body` | Visible text (`正文`) |
| `table` | HTML tables (`表格`) |

**Typical use cases:** job detail pages, public listings, link harvesting, readable body text.

### 2. Project Structure

```
Web-Crawler/
├─ crawl.py              # Entry point & extraction logic
├─ crawl.txt             # Default URL + fields/modes (optional)
├─ run.bat               # Windows: install deps + run crawl.py
├─ requirements.txt
├─ tests/
│  ├─ test_crawl.py
│  └─ fixtures/          # Offline HTML/JSON samples
└─ README.md
```

### 3. Quick Start

```bash
git clone https://github.com/Flin0498/Web-Crawler.git
cd Web-Crawler
python -m pip install -r requirements.txt
python crawl.py https://example.com --mode links
```

Windows (install + run from `crawl.txt`):

```bat
run.bat
```

### 4. User Guide

#### 4.1 What you must specify

1. **URL** — `http://` or `https://`, copied from the browser (watch typos: e.g. `welcome.do` vs `welcome.do.com` → 404).
2. **Extraction** — at least one of:
   - `--mode links|body|table` (repeat `-m` / `--mode` to combine), or
   - `--fields name1,name2` or `-f name1 -f name2`

Without modes/fields (and without `mode=` / `fields=` in `crawl.txt`), the program exits with an error.

#### 4.2 CLI reference

```text
python crawl.py [URL] [-m MODE] [-f FIELD] [--fields NAMES] [-o FILE]

  URL              Page to fetch (optional if crawl.txt defines url=)
  -m, --mode       links | body | table
  -f, --field      Field name (repeatable)
  --fields         Comma-separated field names
  -o, --output     Write JSON to FILE
  -h, --help       Help
```

#### 4.3 Examples

```bash
# Links only
python crawl.py "https://www.baidu.com" --mode links

# Body text
python crawl.py "https://example.com" --mode body

# Tables + title field
python crawl.py "https://example.com" --mode table -f 标题

# Named fields (job detail)
python crawl.py "https://join.qq.com/post_detail.html?postid=1226979621736977408" \
  --fields 岗位名称,岗位职责,岗位要求

# Save JSON
python crawl.py "https://example.com" --mode links -o result.json
```

**PowerShell:** quote URLs that contain `?` or `&`.

#### 4.4 Configuration file (`crawl.txt`)

If you run `python crawl.py` or `run.bat` **without** a URL argument, settings are read from `crawl.txt` in the project folder (then from the current directory).

```ini
# Comments start with #
url=https://join.qq.com/post_detail.html?postid=1226979621736977408
fields=岗位名称,岗位职责,岗位要求

# Alternative:
# url=https://example.com
# mode=links
```

Command-line URL replaces the file URL; CLI modes/fields are merged when provided.

#### 4.5 Built-in field hints (partial)

| Field (examples) | Sources |
|------------------|---------|
| `标题` / `题目` | `<title>`, `og:title`, `h1` |
| `电影名称` / `名称` | `v:itemreviewed`, `h1`, … |
| `评分` / `分数` | `v:average`, `rating_num`, … |
| `简介` / `摘要` | `v:summary`, meta description |
| `岗位名称` … | API fill when HTML is an empty shell |

Custom labels on the page as `Label: value` are also matched when possible.

#### 4.6 Output & exit codes

- **Terminal:** one block per run; link values are printed on a single line (up to 20 shown).
- **JSON (`-o`):** `url`, `ok`, `fields`, `data`, optional `missing`.
- **Exit code `0`** — at least one field extracted; **`1`** — total failure (HTTP 4xx/5xx, bad URL, no fields).

### 5. Testing

```bash
python -m unittest discover -s tests -v
```

Single group:

```bash
python -m unittest discover -s tests -v -k PickFields
```

Tests use local fixtures only (no network).

### 6. Limitations

- No login / cookies — authenticated pages need custom extension.
- Not an LLM — no free-form “understand my sentence” parsing.
- Anti-bot sites may block requests (error message only).
- Respect site terms and applicable laws.

### 7. Documentation note

The **user manual is included in this README** (sections 3–4). For a CLI-only repo this matches common practice on GitHub; split into `docs/` if the project later adds a UI or plugin system.

---

<h2 id="简体中文">简体中文</h2>

### 1. 项目简介

本项目是一个 **纯命令行网页爬虫**（不是大模型 Agent）：

- 输入 **网址** + **要抽取的内容**（字段名或预设模式）
- 请求页面（对部分无正文的详情页会尝试匹配的公开 JSON 接口），**只返回你指定的字段**
- 未配置抽取项、HTTP 失败等情况会明确报错，**默认不会输出整页 HTML**

**预设模式**

| 模式 | 抽取内容 |
|------|----------|
| `links` | 页面链接（字段名 `链接`） |
| `body` | 可见正文（`正文`） |
| `table` | HTML 表格（`表格`） |

**典型场景：** 招聘详情、公开页面链接收集、正文摘录等。

### 2. 目录结构

```
Web-Crawler/
├─ crawl.py              # 主程序
├─ crawl.txt             # 默认网址与字段/模式（可选）
├─ run.bat               # Windows：安装依赖并运行
├─ requirements.txt
├─ tests/
│  ├─ test_crawl.py
│  └─ fixtures/          # 离线测试用 HTML/JSON
└─ README.md
```

### 3. 快速开始

```bash
git clone https://github.com/Flin0498/Web-Crawler.git
cd Web-Crawler
python -m pip install -r requirements.txt
python crawl.py https://example.com --mode links
```

Windows（按 `crawl.txt` 一键运行）：

```bat
run.bat
```

### 4. 用户使用手册

#### 4.1 运行前必须准备

1. **网址**：浏览器地址栏中的 `http://` / `https://` 链接（注意路径勿写错，如 `welcome.do` 与 `welcome.do.com` 会导致 404）。
2. **抽取内容**（至少指定一种）：
   - `--mode links` / `body` / `table`（可多次 `-m`），或
   - `--fields 字段1,字段2` / `-f 字段1 -f 字段2`

未在命令行或 `crawl.txt` 中指定 `mode` / `fields` 时，程序会报错退出。

#### 4.2 命令行参数

```text
python crawl.py [URL] [-m MODE] [-f FIELD] [--fields NAMES] [-o FILE]

  URL              要访问的页面（crawl.txt 中有 url= 时可省略）
  -m, --mode       links | body | table
  -f, --field      字段名（可重复）
  --fields         逗号分隔的多个字段名
  -o, --output     结果写入 JSON 文件
  -h, --help       帮助
```

#### 4.3 使用示例

```bash
# 只抓链接
python crawl.py "https://www.baidu.com" --mode links

# 只抓正文
python crawl.py "https://example.com" --mode body

# 表格 + 标题字段
python crawl.py "https://example.com" --mode table -f 标题

# 招聘详情多个字段
python crawl.py "https://join.qq.com/post_detail.html?postid=1226979621736977408" \
  --fields 岗位名称,岗位职责,岗位要求

# 保存 JSON
python crawl.py "https://example.com" --mode links -o result.json
```

**PowerShell：** 含 `?`、`&` 的 URL 请用双引号包裹。

#### 4.4 配置文件 `crawl.txt`

无 URL 参数时，读取项目目录下的 `crawl.txt`（其次为当前目录下的 `crawl.txt`）。

```ini
# 井号开头为注释
url=https://join.qq.com/post_detail.html?postid=1226979621736977408
fields=岗位名称,岗位职责,岗位要求

# 或使用模式：
# url=https://example.com
# mode=links
```

命令行传入 URL 会覆盖文件中的 `url=`；命令行中的 mode/fields 会与文件配置合并。

#### 4.5 常见字段（节选）

| 字段示例 | 常见来源 |
|----------|----------|
| `标题` / `题目` | `<title>`、`og:title`、`h1` |
| `电影名称` / `名称` | `v:itemreviewed`、`h1` 等 |
| `评分` / `分数` | `v:average`、`rating_num` 等 |
| `简介` / `摘要` | `v:summary`、meta description |
| `岗位名称` 等 | HTML 为空壳时走公开详情接口 |

页面上「标签：内容」形式的文字也会尽量按字段名匹配。

#### 4.6 输出与退出码

- **终端：** 按字段分段显示；链接合并为一行展示（最多 20 条）。
- **JSON（`-o`）：** 含 `url`、`ok`、`fields`、`data`，缺失项在 `missing`。
- **退出码 `0`**：至少抽到一个字段；**`1`**：完全失败（如 404、未匹配任何字段）。

### 5. 测试

```bash
python -m unittest discover -s tests -v
```

按用例组运行：

```bash
python -m unittest discover -s tests -v -k PickFields
```

测试仅使用本地夹具，不访问外网。

### 6. 限制说明

- 不支持登录 Cookie，需登录的页面需自行扩展。
- 非大模型产品，不支持「随便说一句话」式需求解析。
- 部分站点有反爬，只会返回错误提示。
- 请遵守目标网站服务条款与相关法律法规。

### 7. 文档说明

**用户手册已写入本 README**（第 3–4 节），与 GitHub 上多数小型 CLI 项目一致；若后续增加 Web UI、插件等，再拆分到 `docs/` 目录更合适。

---

## License

MIT (add a `LICENSE` file in the repository if not present yet).
