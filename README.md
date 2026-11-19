# deepseek-search

A tiny, dependency-free CLI and agent skill that runs web searches through
DeepSeek's server-side `web_search` tool.

The model is only used to **trigger** the search. Results are parsed straight
from the `web_search_tool_result` content block, so the model never summarizes,
rewrites or paraphrases anything.

```bash
python scripts/dssearch.py "pytorch 2.9 release notes" -n 5
```

```
query: pytorch 2.9 release notes | results: 10 | provider: deepseek (anthropic web_search)
1. PyTorch 2.9 Release Notes
   https://github.com/pytorch/pytorch/releases/tag/v2.9.0
   GitHub | 2026-10-01 | ...
```

## Why

DeepSeek's pricing page states that, since **2026-11-18 12:00 Beijing time**,
a server-side search or page fetch triggered by a model call is **not billed
per call** — only the model's input/output tokens are charged. The standalone
[Search & Fetch APIs](https://api-docs.deepseek.com/guides/search) still cost
5 CNY per 1,000 successful requests.

So a search costs about as much as the tokens used by one tiny request. In
testing a search used 1.7k–9.5k input tokens and 1–44 output tokens. Five
searches moved a 6.76 CNY balance to 6.74 — about 0.02 CNY in tokens total, with
no per-search fee visible.

> This is a promotional policy. DeepSeek can change it at any time. If per-call
> billing comes back, this tool keeps working but costs 5 CNY / 1,000 searches.

## Requirements

- Python 3.8+ (standard library only, nothing to install)
- A DeepSeek API key — https://platform.deepseek.com

## Install

```bash
git clone https://github.com/<you>/deepseek-search.git
cd deepseek-search
export DEEPSEEK_API_KEY=sk-...        # macOS / Linux
# Windows (PowerShell): $env:DEEPSEEK_API_KEY = "sk-..."
```

The key is resolved in this order:

1. `--key`
2. `DEEPSEEK_API_KEY` environment variable
3. `--key-file PATH`
4. `<repo>/.key` (one line, just the key)

`.key` is gitignored. Prefer the environment variable.

## Usage

```bash
python scripts/dssearch.py "query" -n 5
python scripts/dssearch.py "query" --json --usage
python scripts/dssearch.py "query" --native
python scripts/dssearch.py --balance
```

| Flag | Effect |
|---|---|
| `-n, --n` | results to print, default 5 |
| `--native` | declare `deepseek_web_search` instead of the Anthropic `web_search_20250305` tool |
| `--model` | model name, default `deepseek-flash` |
| `--max-uses` | searches allowed in the request, default 1 |
| `--max-tokens` | output budget, default 256; raise it if the tool call gets truncated |
| `--snippet` | characters per snippet, default 240, `0` = unlimited |
| `--timeout` | request timeout in seconds, default 90 |
| `--no-force` | send `tool_choice: auto` instead of forcing a tool call |
| `--json` | normalized JSON: `query`, `queries`, `results`, `citations`, `usage` |
| `--raw` | full Messages API response |
| `--usage` | token usage for the request, printed to stderr |
| `--balance` | print the account balance and exit |
| `--key` / `--key-file` | credential overrides |

### JSON output

```json
{
  "query": "DeepSeek V4.1 发布 新特性",
  "queries": ["DeepSeek V4.1 发布 新特性"],
  "results": [
    {
      "title": "DeepSeek-V4.1-Flash-1017: Wish-Driven Programming Made Real",
      "url": "https://api-docs.deepseek.com/news/news261017/",
      "snippet": "Stronger benchmark performance ...",
      "page_age": "",
      "site_name": "DeepSeek"
    }
  ],
  "citations": [],
  "usage": {
    "input_tokens": 9535,
    "output_tokens": 44,
    "server_tool_use": {
      "web_search_requests": 1,
      "tool_search": 1
    }
  }
}
```

## Use as an agent skill

Copy the directory into your skills folder, for example:

```bash
cp -r deepseek-search ~/.agents/skills/deepseek-search   # Command Code
cp -r deepseek-search ~/.claude/skills/deepseek-search   # Claude Code layout
```

`SKILL.md` contains the frontmatter and the instructions an agent reads. The
script also works fine on its own.

## How it works

1. `POST https://api.deepseek.com/anthropic/v1/messages` with
   `thinking: {"type": "disabled"}`, one server tool
   (`web_search_20250305` or `deepseek_web_search`), and a single user message.
2. The prompt asks the model to pass the query **verbatim** (no rewrite,
   translation, expansion or added dates) and to reply with only `OK`.
3. `tool_choice: {"type": "any"}` forces a tool call in non-thinking mode. If the
   service rejects it, the script retries with `auto`.
4. The model's text is discarded. Results are read from
   `content[].content[]` where `type == "web_search_result"`: `title`, `url`,
   `page_age`, and DeepSeek's extension fields `snippet` / `site_name`.

## Limitations

- **Snippets only.** Page bodies are not returned by the search result block;
  they are carried encrypted. Use a fetch/extract tool for full articles.
- **Verbatim queries.** No multi-step research, follow-up queries or domain
  filters. `--native` may issue several queries in one call.
- **Promotional pricing.** See the note above.
- The Anthropic-compatible endpoint and the `snippet` / `site_name` extension
  fields are DeepSeek-specific and may change.

## Disclaimer

This is an unofficial project. It is not affiliated with, endorsed by, or
sponsored by DeepSeek. "DeepSeek" is a trademark of its respective owner.

## License

MIT — see [LICENSE](LICENSE).

---

## 中文

一个零依赖的小工具：借 DeepSeek 服务端的 `web_search` 做搜索，模型只负责触发，结果直接从
`web_search_tool_result` 块里解析，不让模型转述。

DeepSeek 自 2026-11-18 12:00（北京时间）起，模型调用触发的服务端搜索不计次收费，只算
token；独立的 Search API 仍是 5 元/千次。这是活动政策，未来可能调整。

```bash
export DEEPSEEK_API_KEY=sk-...
python scripts/dssearch.py "查询词" -n 5
python scripts/dssearch.py "查询词" --json --usage
python scripts/dssearch.py --balance
```

只能拿到标题、URL、snippet 和日期，拿不到网页正文。
