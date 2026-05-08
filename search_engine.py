#!/usr/bin/env python3
"""
🔍 PySearch - Google-like Search Engine Tool
Uses multiple free sources with no API key required.
Sources: Bing, SearXNG (public instances), Wikipedia, DuckDuckGo
"""

import sys
import json
import urllib.request
import urllib.parse
import urllib.error
import argparse
import re
import time
import random
from html.parser import HTMLParser


# ─────────────────────────────────────────────
# HTML Parser to strip tags
# ─────────────────────────────────────────────
class HTMLStripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text_parts = []

    def handle_data(self, data):
        self.text_parts.append(data)

    def get_text(self):
        return "".join(self.text_parts)


def strip_html(html: str) -> str:
    s = HTMLStripper()
    s.feed(html)
    return s.get_text()


# ─────────────────────────────────────────────
# Rotating User Agents (avoids bot detection)
# ─────────────────────────────────────────────
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36 Edg/123.0.0.0",
]


def make_request(url: str, extra_headers: dict = None, timeout: int = 12) -> str:
    """Make an HTTP request and return response text."""
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "identity",
        "Connection": "keep-alive",
        "DNT": "1",
        "Upgrade-Insecure-Requests": "1",
    }
    if extra_headers:
        headers.update(extra_headers)

    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        charset = "utf-8"
        content_type = resp.headers.get("Content-Type", "")
        if "charset=" in content_type:
            charset = content_type.split("charset=")[-1].strip().split(";")[0]
        return resp.read().decode(charset, errors="replace")


# ─────────────────────────────────────────────
# Source 1: Bing Search
# ─────────────────────────────────────────────
def search_bing(query: str, max_results: int = 20) -> list:
    """Scrape Bing search results."""
    params = urllib.parse.urlencode({"q": query, "count": max_results, "setlang": "en"})
    url = f"https://www.bing.com/search?{params}"
    results = []

    try:
        html = make_request(url, extra_headers={"Referer": "https://www.bing.com/"})

        # Extract result blocks
        blocks = re.findall(r'<li class="b_algo".*?</li>', html, re.DOTALL)

        for block in blocks:
            if len(results) >= max_results:
                break

            # Title + URL from <h2><a href="...">Title</a></h2>
            title_match = re.search(
                r'<h2[^>]*>\s*<a[^>]+href="([^"#][^"]*)"[^>]*>(.*?)</a>', block, re.DOTALL
            )
            # Snippet from <p ...>text</p>
            snip_match = re.search(r'<p[^>]*>(.*?)</p>', block, re.DOTALL)

            if title_match:
                href = title_match.group(1).strip()
                title = strip_html(title_match.group(2)).strip()
                snippet = strip_html(snip_match.group(1)).strip() if snip_match else ""

                if href.startswith("http") and "bing.com" not in href and title:
                    results.append({
                        "title": title,
                        "url": href,
                        "snippet": re.sub(r'\s+', ' ', snippet)[:250],
                        "source": "Bing",
                    })

    except Exception as e:
        raise RuntimeError(f"Bing: {e}")

    return results


# ─────────────────────────────────────────────
# Source 2: SearXNG Public Instances
# ─────────────────────────────────────────────
SEARXNG_INSTANCES = [
    "https://searx.be",
    "https://searxng.world",
    "https://search.inetol.net",
    "https://searx.tiekoetter.com",
    "https://opnxng.com",
    "https://paulgo.io",
    "https://searx.bnyro.com",
]


def search_searxng(query: str, max_results: int = 10) -> list:
    """Query public SearXNG instances (privacy-respecting meta-search engine)."""
    results = []
    instances = SEARXNG_INSTANCES[:]
    random.shuffle(instances)

    last_error = None
    for instance in instances:
        try:
            params = urllib.parse.urlencode({
                "q": query,
                "format": "json",
                "categories": "general",
                "language": "en",
                "time_range": "",
                "safesearch": "0",
            })
            url = f"{instance}/search?{params}"
            raw = make_request(url, extra_headers={
                "Referer": instance,
                "Accept": "application/json, text/javascript, */*",
            }, timeout=8)
            data = json.loads(raw)

            for item in data.get("results", [])[:max_results]:
                url_val = item.get("url", "")
                title   = item.get("title", "")
                snippet = item.get("content", "")
                if url_val and title:
                    results.append({
                        "title": title,
                        "url": url_val,
                        "snippet": snippet[:250],
                        "source": f"SearXNG",
                    })

            if results:
                return results  # Got results — stop trying other instances

        except Exception as e:
            last_error = e
            continue

    if not results and last_error:
        raise RuntimeError(f"SearXNG (all instances failed): {last_error}")

    return results


# ─────────────────────────────────────────────
# Source 3: Wikipedia OpenSearch
# ─────────────────────────────────────────────
def search_wikipedia(query: str, max_results: int = 3) -> list:
    """Search Wikipedia using its open API."""
    params = urllib.parse.urlencode({
        "action": "opensearch",
        "search": query,
        "limit": max_results,
        "format": "json",
        "namespace": "0",
    })
    url = f"https://en.wikipedia.org/w/api.php?{params}"
    results = []

    try:
        raw = make_request(url)
        data = json.loads(raw)
        titles       = data[1] if len(data) > 1 else []
        descriptions = data[2] if len(data) > 2 else []
        urls         = data[3] if len(data) > 3 else []

        for i, page_url in enumerate(urls[:max_results]):
            results.append({
                "title":   f"Wikipedia: {titles[i]}" if i < len(titles) else "Wikipedia",
                "url":     page_url,
                "snippet": descriptions[i][:200] if i < len(descriptions) else "",
                "source":  "Wikipedia",
            })

    except Exception as e:
        raise RuntimeError(f"Wikipedia: {e}")

    return results


# ─────────────────────────────────────────────
# Source 4: DuckDuckGo (with session warm-up)
# ─────────────────────────────────────────────
def search_duckduckgo(query: str, max_results: int = 10) -> list:
    """Try DuckDuckGo HTML search with proper session handling."""
    results = []

    # Warm up session
    try:
        make_request("https://duckduckgo.com/", timeout=6)
        time.sleep(random.uniform(0.3, 0.7))
    except Exception:
        pass

    params = urllib.parse.urlencode({"q": query, "kl": "us-en", "kp": "-1", "kaf": "1"})
    url = f"https://html.duckduckgo.com/html/?{params}"

    try:
        html = make_request(url, extra_headers={
            "Referer": "https://duckduckgo.com/",
            "Origin":  "https://duckduckgo.com",
        })

        # Each result is in a div.result
        blocks = re.findall(
            r'<div[^>]+class="[^"]*result[^"]*"[^>]*>(.*?)</div>\s*</div>\s*</div>',
            html, re.DOTALL
        )

        for block in blocks:
            if len(results) >= max_results:
                break

            url_match  = re.search(r'class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>', block, re.DOTALL)
            snip_match = re.search(r'class="result__snippet"[^>]*>(.*?)</a>', block, re.DOTALL)

            if url_match:
                href    = url_match.group(1)
                title   = strip_html(url_match.group(2)).strip()
                snippet = strip_html(snip_match.group(1)).strip() if snip_match else ""

                # DDG uses redirect URLs — extract real URL
                uddg = re.search(r"uddg=([^&]+)", href)
                real_url = urllib.parse.unquote(uddg.group(1)) if uddg else href

                if real_url.startswith("http") and title:
                    results.append({
                        "title":   title,
                        "url":     real_url,
                        "snippet": snippet[:250],
                        "source":  "DuckDuckGo",
                    })

    except Exception as e:
        raise RuntimeError(f"DuckDuckGo: {e}")

    return results


# ─────────────────────────────────────────────
# Deduplicate results
# ─────────────────────────────────────────────
def deduplicate(results: list) -> list:
    seen, unique = set(), []
    for r in results:
        key = re.sub(r'^https?://', '', r.get("url", "").rstrip("/").lower())
        if key and key not in seen:
            seen.add(key)
            unique.append(r)
    return unique


# ─────────────────────────────────────────────
# Main Search Orchestrator
# ─────────────────────────────────────────────
def search(query: str, max_results: int = 10) -> list:
    all_results = []

    sources = [
        ("Bing",        lambda: search_bing(query, max_results)),
        ("SearXNG",     lambda: search_searxng(query, max_results)),
        ("Wikipedia",   lambda: search_wikipedia(query, 3)),
        ("DuckDuckGo",  lambda: search_duckduckgo(query, max_results)),
    ]

    for name, fn in sources:
        print(f"  ⏳ Trying {name}...", file=sys.stderr, end=" ", flush=True)
        try:
            res = fn()
            if res:
                print(f"✅  {len(res)} results", file=sys.stderr)
            else:
                print(f"⚠️  0 results", file=sys.stderr)
            all_results.extend(res)
        except Exception as e:
            print(f"❌  {e}", file=sys.stderr)

        # Stop early once we have enough unique results
        if len(deduplicate(all_results)) >= max_results:
            break

    return deduplicate(all_results)[:max_results]


# ─────────────────────────────────────────────
# Display Results
# ─────────────────────────────────────────────
def display_results(results: list, query: str, output_format: str = "pretty"):
    if not results:
        print("\n❌ No results found. Check your internet connection or try again.\n")
        return

    if output_format == "json":
        print(json.dumps(results, indent=2, ensure_ascii=False))
        return

    if output_format == "urls":
        for r in results:
            print(r["url"])
        return

    # Pretty print
    print("\n" + "═" * 68)
    print(f'  🔍  Results for: "{query}"   ({len(results)} found)')
    print("═" * 68)

    for i, r in enumerate(results, 1):
        title   = (r.get("title") or "No title").strip()
        url     = r.get("url", "")
        snippet = (r.get("snippet") or "").strip()
        source  = r.get("source", "")

        # Trim long titles
        if len(title) > 80:
            title = title[:77] + "..."

        print(f"\n  [{i}] {title}")
        print(f"       🔗 {url}")

        if snippet:
            snippet = re.sub(r'\s+', ' ', snippet)
            words, line, lines = snippet.split(), "", []
            for w in words:
                if len(line) + len(w) + 1 > 62:
                    lines.append(line)
                    line = w
                else:
                    line = f"{line} {w}".strip()
            if line:
                lines.append(line)
            for ln in lines:
                print(f"       {ln}")

        if source:
            print(f"       \033[90m[{source}]\033[0m")

    print("\n" + "═" * 68 + "\n")


# ─────────────────────────────────────────────
# Interactive REPL Mode
# ─────────────────────────────────────────────
def interactive_mode(max_results: int, output_format: str):
    print("╔══════════════════════════════════════════╗")
    print("║   🔍  PySearch — Google-like Search Tool ║")
    print("║   Type 'quit' or 'exit' to stop          ║")
    print("╚══════════════════════════════════════════╝\n")

    while True:
        try:
            query = input("Search > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n👋 Goodbye!")
            break

        if not query:
            continue
        if query.lower() in ("quit", "exit", "q"):
            print("👋 Goodbye!")
            break

        print(f"\n🔍 Searching for: \"{query}\"...", file=sys.stderr)
        results = search(query, max_results)
        display_results(results, query, output_format)


# ─────────────────────────────────────────────
# CLI Entry Point
# ─────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="🔍 PySearch — Google-like search engine in Python (no API key needed)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python search_engine.py "machine learning tutorials"
  python search_engine.py "climate change" -n 5
  python search_engine.py "python tips" --format json
  python search_engine.py "bitcoin" --format urls
  python search_engine.py            # interactive REPL mode
        """
    )
    parser.add_argument("query", nargs="?", help="Search query (omit for interactive REPL mode)")
    parser.add_argument("-n", "--num", type=int, default=10, metavar="N",
                        help="Number of results to return (default: 10)")
    parser.add_argument("--format", choices=["pretty", "json", "urls"], default="pretty",
                        help="Output format: pretty (default), json, or urls-only")

    args = parser.parse_args()

    if args.query:
        print(f"\n🔍 Searching for: \"{args.query}\"...", file=sys.stderr)
        results = search(args.query, args.num)
        display_results(results, args.query, args.format)
    else:
        interactive_mode(args.num, args.format)


if __name__ == "__main__":
    main()