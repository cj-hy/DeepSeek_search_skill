#!/usr/bin/env python3
"""Web search through DeepSeek's server-side web_search tool.

Since 2026-11-18 12:00 Beijing time, a search triggered by a model call is not
billed per call; only the model's input/output tokens are charged.

The script sends a minimal Messages request to the Anthropic-compatible
endpoint, forces one search, and prints the structured results taken from the
`web_search_tool_result` content block. The model's own answer is not used.
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

MESSAGES_URL = "https://api.deepseek.com/anthropic/v1/messages"
BALANCE_URL = "https://api.deepseek.com/user/balance"
DEFAULT_MODEL = "deepseek-flash"
KEY_FILE = Path(__file__).resolve().parent.parent / ".key"

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")


def die(message, code=3):
    sys.stderr.write(str(message).rstrip() + "\n")
    raise SystemExit(code)


def resolve_key(cli_key, key_file):
    key = cli_key or os.environ.get("DEEPSEEK_API_KEY")
    if not key:
        path = Path(key_file).expanduser() if key_file else KEY_FILE
        if path.is_file():
            key = path.read_text(encoding="utf-8").strip()
    if not key:
        die("no key: set DEEPSEEK_API_KEY, pass --key, or write it to {}".format(KEY_FILE), 2)
    return key


def http_json(request, timeout):
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", "replace")
        return {"_http_error": error.code, "_detail": detail}
    except urllib.error.URLError as error:
        die("network error: {}".format(error.reason))


def search_request(args, key, force):
    if args.native:
        tools = [{"type": "deepseek_web_search", "name": "deepseek_web_search"}]
    else:
        tools = [{
            "type": "web_search_20250305",
            "name": "web_search",
            "max_uses": args.max_uses,
        }]

    prompt = (
        "Call the web search tool exactly once. Pass the user's query verbatim as "
        "the search query: do not rewrite, translate, expand, or add dates. "
        "After the search finishes, reply with exactly: OK\n\n"
        "Query: {}".format(args.query)
    )

    body = {
        "model": args.model,
        "max_tokens": args.max_tokens,
        "thinking": {"type": "disabled"},
        "tools": tools,
        "messages": [{"role": "user", "content": prompt}],
    }
    if force:
        body["tool_choice"] = {"type": "any"}

    request = urllib.request.Request(
        MESSAGES_URL,
        data=json.dumps(body).encode("utf-8"),
        method="POST",
        headers={
            "content-type": "application/json",
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
        },
    )
    return http_json(request, args.timeout)


def extract(payload):
    queries = []
    results = []
    citations = []
    blocks = payload.get("content") or []
    for block in blocks:
        kind = block.get("type")
        if kind == "server_tool_use":
            value = (block.get("input") or {})
            query = value.get("queries") or value.get("query")
            if isinstance(query, list):
                queries.extend(str(item) for item in query)
            elif query:
                queries.append(str(query))
        elif kind == "web_search_tool_result":
            content = block.get("content")
            if not isinstance(content, list):
                continue
            for item in content:
                if item.get("type") != "web_search_result":
                    continue
                results.append({
                    "title": item.get("title") or "",
                    "url": item.get("url") or "",
                    "snippet": item.get("snippet") or "",
                    "page_age": item.get("page_age") or "",
                    "site_name": item.get("site_name") or "",
                })
        elif kind == "text":
            for citation in (block.get("citations") or []):
                if citation.get("url"):
                    citations.append({
                        "url": citation.get("url"),
                        "title": citation.get("title") or "",
                        "cited_text": citation.get("cited_text") or "",
                    })
    return queries, results, citations


def fetch_balance(key, timeout):
    request = urllib.request.Request(
        BALANCE_URL,
        headers={"Authorization": "Bearer {}".format(key)},
    )
    return http_json(request, timeout)


def print_text(args, queries, results):
    if len(queries) > 1:
        sys.stderr.write("queries: {}\n".format(" | ".join(queries)))

    show = results[:args.n]
    print("query: {} | results: {} | provider: deepseek ({})".format(
        args.query, len(results), "native" if args.native else "anthropic web_search"))

    if not show:
        print("(no results)")
        return

    for index, item in enumerate(show, 1):
        title = item["title"] or "(untitled)"
        print("{}. {}".format(index, title))
        print("   {}".format(item["url"]))
        meta = [part for part in (item["page_age"], item["site_name"]) if part]
        snippet = item["snippet"]
        if args.snippet and len(snippet) > args.snippet:
            snippet = snippet[:args.snippet].rstrip() + "..."
        head = "   "
        if meta:
            head += " | ".join(meta) + (" | " if snippet else "")
        print(head + snippet if snippet else head.rstrip())


def print_json(data):
    print(json.dumps(data, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(
        description="Search the web through DeepSeek's server-side web_search tool.")
    parser.add_argument("query", nargs="*", help="search query")
    parser.add_argument("-n", "--n", type=int, default=5, help="results to print (default 5)")
    parser.add_argument("--native", action="store_true",
                        help="use deepseek_web_search instead of the Anthropic web_search tool")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="model name (default deepseek-flash)")
    parser.add_argument("--max-uses", type=int, default=1, help="max searches per request (default 1)")
    parser.add_argument("--max-tokens", type=int, default=256, help="output token budget (default 256)")
    parser.add_argument("--snippet", type=int, default=240, help="snippet cap, 0 = unlimited (default 240)")
    parser.add_argument("--timeout", type=float, default=90, help="request timeout in seconds (default 90)")
    parser.add_argument("--no-force", action="store_true", help="let the model decide whether to search")
    parser.add_argument("--json", action="store_true", help="print normalized JSON")
    parser.add_argument("--raw", action="store_true", help="print the full API response")
    parser.add_argument("--usage", action="store_true", help="print token usage to stderr")
    parser.add_argument("--balance", action="store_true", help="print account balance and exit")
    parser.add_argument("--key", help="API key (defaults to DEEPSEEK_API_KEY)")
    parser.add_argument("--key-file", help="file holding the API key (default: <skill>/.key)")
    args = parser.parse_args()

    args.query = " ".join(args.query)
    if not args.balance and not args.query:
        parser.error("query is required")
    key = resolve_key(args.key, args.key_file)

    if args.balance:
        print_json(fetch_balance(key, args.timeout))
        return

    payload = search_request(args, key, force=not args.no_force)

    if "_http_error" in payload:
        if payload["_http_error"] == 400 and not args.no_force:
            payload = search_request(args, key, force=False)
        if "_http_error" in payload:
            die("HTTP {}: {}".format(payload["_http_error"], payload["_detail"]))

    if args.raw:
        print_json(payload)
        return

    queries, results, citations = extract(payload)

    if args.usage:
        sys.stderr.write("usage: {}\n".format(json.dumps(payload.get("usage") or {}, ensure_ascii=False)))

    if args.json:
        print_json({
            "query": args.query,
            "queries": queries,
            "results": results[:args.n],
            "citations": citations,
            "usage": payload.get("usage") or {},
        })
        return

    print_text(args, queries, results)


if __name__ == "__main__":
    main()
