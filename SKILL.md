---
name: deepseek-search
description: Search the live web through DeepSeek's server-side web_search tool. Since 2026-11-18 12:00 Beijing time a model-triggered server-side search is not billed per call, only input/output tokens. Use when the user asks to search with DeepSeek (用 DeepSeek 搜 / 免搜索费搜一下), wants to avoid per-search fees, or when the Tavily web-search skill has no credits left.
argument-hint: "<query> [-n 5] [--native] [--json]"
---

# DeepSeek Search

One capability: run a real web search through DeepSeek's server-side search and
print the structured results. No model answer is used; the results are read
straight from the `web_search_tool_result` block.

Per DeepSeek's pricing page, since 2026-11-18 12:00 Beijing time a server-side
search triggered by a model call is **not billed per call** — only the model's
input/output tokens are charged. The standalone Search API still costs 5 元 per
1,000 successful requests; this skill does not use it.

## Setup

Needs a DeepSeek API key, resolved in this order: `--key`, the
`DEEPSEEK_API_KEY` environment variable, `--key-file`, then `<skill-root>/.key`
(one line, just the key). Get a key at <https://platform.deepseek.com>.

No third-party packages: the script is pure Python standard library.

## Run

The skill root is the directory containing this `SKILL.md`; the script lives at
`<skill-root>/scripts/dssearch.py`. On Windows call `python`, not `python3`.

```bash
python "<skill-root>/scripts/dssearch.py" "pytorch 2.9 release notes" -n 5
```

## Options

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
| `--balance` | print the account balance and exit (useful for cost checks) |
| `--key` | API key, defaults to `DEEPSEEK_API_KEY` |
| `--key-file` | file holding the key, default `<skill-root>/.key` |

## How it works

1. `POST https://api.deepseek.com/anthropic/v1/messages` with
   `thinking: {"type": "disabled"}` and one server tool (`web_search_20250305`
   or `deepseek_web_search`).
2. The prompt asks the model to pass the query verbatim (no rewrite, translation,
   expansion or added dates) and to reply with only `OK` after the search.
3. `tool_choice: {"type": "any"}` forces the search in non-thinking mode. If the
   service rejects that, the script retries with `auto` and the prompt still asks
   for one search.
4. The model's reply text is ignored. Results come from
   `content[].content[]` where `type == "web_search_result"`: `title`, `url`,
   `page_age`, plus DeepSeek's extension fields `snippet` / `site_name` when the
   service returns them.

## Output

```
query: pytorch 2.9 release notes | results: 5 | provider: deepseek (anthropic web_search)
1. PyTorch 2.9 Release Notes
   https://github.com/pytorch/pytorch/releases/tag/v2.9.0
   2026-10-01 | ...
```

## Rules

- Cite the URL for every fact taken from the results.
- Page bodies are not available: search results carry titles, URLs, snippets
  and dates only. Use the `web-fetch` skill when the full article is needed.
- The free window is a DeepSeek promotion and can change. If billing changes,
  this skill still works but each search costs 5 元 / 1,000 calls.
- `(no results)` is a valid answer: rephrase once, then report that nothing was
  found.
- Exit code 2 means missing key or bad usage; exit code 3 means the request
  failed after the retry. Report the error instead of guessing.
