# Detailed Code Documentation And Handover Guide

This document explains the complete codebase in enough detail that a new developer can understand the project without reading every file first.

Project path:

```text
D:\vs_project_search_engine\web_search_agent
```

## 1. What This Project Does

This project is a Python web-search agent. A user can ask any query through the local web UI, API, or CLI. The system then:

1. Understands the query.
2. Generates better search queries.
3. Searches DuckDuckGo.
4. Scores and filters sources.
5. Optionally asks an LLM to rerank sources.
6. Optionally fetches page content.
7. Generates an answer using the best available sources.
8. Shows sources, relevance scores, confidence information, and token usage.

The system has two main search modes:

- Normal search flow: used by `main.py`, `api.py`, and default CLI.
- Enhanced CLI flow: used by `py cli.py --enhanced "query"` and adds quality/trust/confidence scoring.

## 2. High-Level Architecture

```text
User Query
  |
  |-- api.py / cli.py / main.py
  |
  |-- DuckDuckGoSearchAgent.search()
        |
        |-- SearchCache
        |     |-- Returns cached result if available
        |
        |-- SourceDiscovery
        |     |-- Query understanding
        |     |-- LLM query planner, if OpenAI key exists
        |     |-- Query rewriting
        |     |-- DuckDuckGo search
        |     |-- Heuristic relevance scoring
        |     |-- LLM reranking, if OpenAI key exists
        |     |-- Low-quality result filtering
        |
        |-- ContentProcessor, optional
        |     |-- Fetches and extracts full page content
        |
        |-- LightweightAnalyzer
        |     |-- Extracts keyword insights
        |     |-- LLM answer generation, if OpenAI key exists
        |     |-- Plain fallback answer if no LLM
        |
        |-- ResponseFormatter / API JSON / Web UI
```

Enhanced CLI flow:

```text
py cli.py --enhanced "query"
  |
  |-- EnhancedSearchCLI
        |
        |-- EnhancedSearcher
        |     |-- DuckDuckGo search
        |     |-- Quality scoring
        |     |-- Domain authority
        |     |-- Content type detection
        |     |-- Recency flags
        |
        |-- EnhancedAnalyzer
              |-- Fact extraction
              |-- Source trust scoring
              |-- Cross-source consistency check
              |-- Confidence score
              |-- LLM answer with confidence indicators
```

## 3. Runtime Entry Points

### 3.1 `py api.py`

Starts FastAPI on:

```text
http://localhost:8000
```

This is the easiest way to test the agent in a browser.

Important API examples:

```text
http://localhost:8000/api/search?query=what%20is%20sanctioned%20fsi
http://localhost:8000/api/search?query=what%20is%20government%20rate%20in%20wakad&no_cache=true
```

Use `no_cache=true` when testing relevance changes because otherwise old cached results may appear.

### 3.2 `py main.py`

Starts a simple interactive terminal loop using `DuckDuckGoSearchAgent`.

Commands inside the loop:

```text
stats
exit
quit
q
```

### 3.3 `py cli.py "query"`

Runs the direct CLI search flow.

Examples:

```powershell
py cli.py "latest AI model updates"
py cli.py "what is sanctioned fsi"
py cli.py "what is government rate in wakad"
```

### 3.4 `py cli.py --enhanced "query"`

Runs the enhanced CLI flow with:

- relevance score
- quality score
- trust score
- confidence level
- source consistency information

Example:

```powershell
py cli.py --enhanced "what is government rate in wakad"
```

## 4. Environment And Configuration

### 4.1 `.env`

The real `.env` file is local only and must not be pushed to GitHub.

`.gitignore` ignores:

```text
.env
.env.*
```

`.env.example` is safe to push.

### 4.2 Required OpenAI Key For LLM Features

LLM features work only when this exists:

```env
OPENAI_API_KEY=your_key_here
```

If the key is missing:

- DuckDuckGo search still works.
- LLM query planning is disabled.
- LLM reranking is disabled.
- LLM answer generation is disabled.
- The system falls back to basic search result formatting.

### 4.3 Main Config Values

Defined in `config.py`.

| Variable | Default | Role |
|---|---:|---|
| `DDG_MAX_RESULTS` | `10` | Default DuckDuckGo result count. |
| `DDG_TIMEOUT` | `10` | Intended search timeout setting. |
| `DDG_REGION` | `wt-wt` | Default region setting from env, though `DuckDuckGoSearcher` currently uses `in-en`. |
| `OPENAI_API_KEY` | empty | Enables OpenAI LLM features. |
| `USE_LLM` | bool of key | True when an API key exists. |
| `LLM_MODEL` | `gpt-4o-mini` | Main chat model for planning, reranking, and answering. |
| `MAX_TOKENS` | `500` | Max answer tokens for answer generation. |
| `MAX_CONTENT_LENGTH` | `5000` | Maximum extracted page content length. |
| `EXTRACT_READABLE` | `true` | Whether to use Trafilatura first. |
| `CACHE_ENABLED` | `true` | Enables DiskCache. |
| `CACHE_TTL` | `3600` | Cache lifetime in seconds. |
| `CACHE_DIR` | `data/cache` | Local cache directory. |
| `REQUEST_DELAY` | `1.0` | Intended delay between requests. |
| `MAX_RETRIES` | `3` | Intended retry setting. |
| `DEFAULT_FORMAT` | `markdown` | Default response format. |
| `MAX_RESULTS_IN_RESPONSE` | `5` | Number of sources shown. |
| `API_HOST` | `0.0.0.0` | FastAPI host. |
| `API_PORT` | `8000` | FastAPI port. |

## 5. Tools And Libraries Used

### Search

| Tool | Package | File | Purpose |
|---|---|---|---|
| DuckDuckGo | `ddgs` / `duckduckgo-search` | `search_agent/searcher.py` | Main web search provider returning real URLs. |
| OpenAI web search preview | `openai` | `LLMBasedSearcher` in `searcher.py` | Optional older LLM web-search path. It can return synthetic answers without URLs, so it is not the preferred direct source path. |

### LLM

| Tool | File | Purpose |
|---|---|---|
| OpenAI Chat Completions | `source_discovery.py` | Query planning and result reranking. |
| OpenAI Chat Completions | `analyzer.py` | Final answer generation. |
| OpenAI Chat Completions | `cli.py` | Direct CLI answer generation in `DirectSearchAgent`. |
| `gpt-4o-mini` | configured in `config.py` | Main low-cost model. |
| `gpt-4o` | `LLMBasedSearcher` | Optional web-search-preview model. |
| `tiktoken` | `analyzer.py` | Token encoder setup. |

### Web Server

| Tool | File | Purpose |
|---|---|---|
| FastAPI | `api.py` | Localhost API and web UI. |
| Uvicorn | `api.py` | Runs the server. |
| Pydantic | `api.py` | Defines `SearchRequest`. |

### Content Extraction

| Tool | File | Purpose |
|---|---|---|
| Requests | `processor.py` | Fetch page HTML. |
| BeautifulSoup | `processor.py` | Parse and clean HTML. |
| Trafilatura | `processor.py` | First strategy for readable text extraction. |
| Readability | `processor.py` | Second extraction strategy. |
| Newspaper3k | `processor.py` | Imported as an optional article extraction dependency. |
| Tenacity | `processor.py` | Retry fetch failures. |

### Cache And Utilities

| Tool | File | Purpose |
|---|---|---|
| DiskCache | `cache.py` | Persistent search result cache. |
| python-dotenv | `config.py` | Loads `.env`. |
| hashlib | `cache.py`, `searcher.py` | Generates stable cache/search hashes. |

Dependencies listed but not heavily used in active code:

- `redis`
- `rich`
- `prometheus-client`
- `structlog`
- `jinja2`

## 6. File-By-File Deep Documentation

## 6.1 `config.py`

### Role

`config.py` is the central configuration file. It loads environment variables from `.env` and exposes a singleton:

```python
config = Config()
```

All other modules import:

```python
from config import config
```

### Step-By-Step Behavior

1. Imports `os`.
2. Imports and calls `load_dotenv()`.
3. Defines class `Config`.
4. Reads every needed setting from environment variables.
5. Converts strings to correct types:
   - `int`
   - `float`
   - `bool`
6. Creates one global `config` object.

### Rules Defined In This File

- If `OPENAI_API_KEY` is empty, `USE_LLM` becomes `False`.
- If `OPENAI_API_KEY` exists, `USE_LLM` becomes `True`.
- Boolean env values are treated as true only when string is `"true"` after lowercasing.
- Default model is `gpt-4o-mini`.
- Default cache directory is `data/cache`.

### Used By

- `main.py`
- `api.py`
- `cli.py`
- `search_agent/searcher.py`
- `search_agent/source_discovery.py`
- `search_agent/analyzer.py`
- `search_agent/processor.py`
- `search_agent/cache.py`

## 6.2 `main.py`

### Role

`main.py` is the main application orchestrator. It defines the central class:

```python
DuckDuckGoSearchAgent
```

This class connects search, discovery, analysis, formatting, and caching.

### Important Constant

```python
SEARCH_CACHE_VERSION = "source-discovery-v5"
```

This version is prefixed into cache keys. When ranking logic changes, this value should be bumped so old cached poor results do not appear.

### Class: `DuckDuckGoSearchAgent`

#### `__init__()`

Creates:

```python
self.searcher = DuckDuckGoSearcher()
self.discovery = SourceDiscovery(self.searcher)
self.processor = ContentProcessor()
self.analyzer = LightweightAnalyzer()
self.formatter = ResponseFormatter()
self.cache = SearchCache() if config.CACHE_ENABLED else None
```

Also initializes stats:

```python
queries
cache_hits
cache_misses
total_tokens
total_cost
```

#### `search(query, max_results=5, fetch_content=False, use_cache=True)`

This is the core workflow.

Step by step:

1. Builds a cache key:

   ```python
   cache_query = f"{SEARCH_CACHE_VERSION}:{query}"
   ```

2. Checks cache if `use_cache=True`.

3. If cache hit:

   - increments `cache_hits`
   - adds `cached=True`
   - returns cached data

4. If cache miss:

   - increments `cache_misses`
   - increments `queries`

5. Runs source discovery:

   ```python
   discovery = self.discovery.discover(query, max_results)
   ```

6. Converts discovered results into dictionaries.

7. If `fetch_content=True`, fetches full content for top 3 URLs using `ContentProcessor`.

8. Records analyzer token usage before answer generation.

9. Checks whether analysis is needed:

   ```python
   self.analyzer.needs_analysis(query, results_dict)
   ```

10. Extracts keyword insights.

11. Generates final analysis/answer.

12. Builds output dictionary with:

   - query
   - success
   - discovery
   - discovery_token_usage
   - results_count
   - results
   - analysis
   - timestamp

13. Calculates per-query answer token usage by subtracting before/after token counters.

14. Adds total token/cost stats.

15. Saves output to cache.

16. Returns output.

### Output Shape

```python
{
    "query": "...",
    "success": True,
    "discovery": {...},
    "discovery_token_usage": {...},
    "results_count": 5,
    "results": [...],
    "analysis": "...",
    "timestamp": "...",
    "token_usage": {...}
}
```

### Other Methods

#### `search_async()`

Runs `search()` in an executor for async usage.

#### `search_news()`

Uses `DuckDuckGoSearcher.search_news()`.

#### `format_response()`

Delegates to `ResponseFormatter`.

Formats:

- markdown
- json
- plain text

#### `get_stats()`

Returns:

- query counts
- cache stats
- token usage
- LLM enabled state
- model name

### Main CLI Loop

The `main()` function lets a user type searches interactively.

Special commands:

- `exit`
- `quit`
- `q`
- `stats`

## 6.3 `api.py`

### Role

`api.py` exposes the search agent over HTTP and provides a very simple browser UI.

### Main Objects

```python
app = FastAPI(...)
agent = DuckDuckGoSearchAgent()
```

`agent` is created once when the server starts.

### Class: `SearchRequest`

Pydantic model:

```python
query: str
max_results: Optional[int]
format: Optional[str]
```

This is currently defined but the main search endpoint uses query parameters, not POST body.

### Endpoint: `/`

Returns HTML with:

- search input
- search button
- JavaScript fetch call to `/api/search`
- display area for:
  - cached result notice
  - analysis
  - answer token usage
  - search brain token usage
  - query discovery info
  - result relevance scores
  - source URLs

### Endpoint: `/api/search`

Signature:

```python
async def search(query: str, max_results: int, no_cache: bool = False)
```

Step by step:

1. Receives query from URL parameter.
2. Receives optional `max_results`.
3. Receives optional `no_cache`.
4. Calls:

   ```python
   agent.search(query, max_results, use_cache=not no_cache)
   ```

5. Returns JSON result.

### Endpoint: `/api/stats`

Returns:

```python
agent.get_stats()
```

### Endpoint: `/health`

Returns:

```json
{
  "status": "healthy",
  "llm_enabled": true,
  "cache_enabled": true
}
```

### Rules In This File

- Browser UI always calls `/api/search?query=...`.
- Cache bypass must be done manually through API URL with `no_cache=true`.
- UI displays token usage only if token data exists.
- Cached response shows "No new LLM tokens were used".

## 6.4 `cli.py`

### Role

`cli.py` provides multiple command-line search modes:

- direct search
- smart real-estate search
- news search
- enhanced search with trust/confidence scoring
- interactive mode

### Imports

Uses:

- `DuckDuckGoSearcher`
- `EnhancedSearcher`
- `EnhancedAnalyzer`
- `SourceDiscovery`
- `config`
- OpenAI client inside some classes if key exists

### Class: `DirectSearchAgent`

Default direct CLI search.

#### Rules

It disambiguates common acronyms:

| Acronym | Meaning / Context |
|---|---|
| `fsi` | Floor Space Index |
| `udcpr` | Maharashtra development control regulations |
| `dcpr` | Development Control Promotion Regulations |
| `rera` / similar | Real estate regulatory context |
| `oc` | Occupancy Certificate |
| `cc` | Completion Certificate |

#### `search_direct()`

Step by step:

1. Stores original query.
2. Optionally disambiguates acronyms.
3. Uses `SourceDiscovery` to get real URLs.
4. Converts result dictionaries.
5. If OpenAI client exists, asks LLM for answer using the found sources.
6. Tracks token usage.
7. Returns result dictionary.

#### `_get_llm_answer()`

Builds a prompt from search results and asks the configured model to answer.

Rules:

- If query contains FSI, warns model that FSI means Floor Space Index, not Forest Survey/financial sanctions.
- Uses titles and snippets as answer context.
- Tracks:
  - input tokens
  - output tokens
  - total tokens
  - estimated cost

### Class: `QueryOptimizer`

Used by smart mode.

Purpose:

- Understand real-estate query intent.
- Extract:
  - intent
  - location
  - property type
  - key topics
  - time context
- Generate better real-estate search queries.

If LLM is unavailable, falls back to keyword-based detection.

### Class: `SmartSearchCLI`

Uses:

- `DuckDuckGoSearcher`
- `QueryOptimizer`

Step by step:

1. Understand query intent.
2. Generate optimized queries.
3. Try each query until results are found.
4. Format results in terminal.

### Class: `EnhancedSearchCLI`

New enhanced CLI mode.

Used through:

```powershell
py cli.py --enhanced "query"
```

Uses:

- `EnhancedSearcher`
- `EnhancedAnalyzer`

Step by step:

1. Runs `EnhancedSearcher.search_with_quality()`.
2. Converts `SearchResult` objects to dictionaries.
3. Runs `EnhancedAnalyzer.analyze_with_confidence()`.
4. Prints:
   - confidence level
   - source count
   - high-trust source count
   - answer
   - trust score per source
   - relevance score
   - quality score
   - domain authority
   - contradictions
   - token usage

### CLI Arguments

| Argument | Purpose |
|---|---|
| `query` | Search query words. |
| `-n`, `--max-results` | Number of results. |
| `--news` | Search news only. |
| `--smart` | Use smart real-estate query expansion. |
| `--enhanced` | Use enhanced quality/trust/confidence mode. |
| `-i`, `--interactive` | Interactive terminal loop. |
| `--direct` | Explicit direct search mode. |

## 6.5 `search_agent/searcher.py`

### Role

This file contains search provider classes and the shared `SearchResult` dataclass.

### Dataclass: `SearchResult`

Fields:

| Field | Purpose |
|---|---|
| `url` | Source URL. |
| `title` | Result title. |
| `snippet` | Search result snippet. |
| `source` | Provider name, e.g. `duckduckgo`. |
| `rank` | Original search rank. |
| `content` | Optional fetched content. |
| `relevance_score` | Query relevance. |
| `quality_score` | Source quality score. |
| `content_type` | `html`, `pdf`, or `json`. |
| `fetch_time` | Reserved for future fetch timing. |
| `word_count` | Snippet/content word count. |
| `has_date` | Whether result contains date/year. |
| `domain_authority` | Score from known domain list. |
| `is_recent` | Whether result looks recent. |

### Class: `DuckDuckGoSearcher`

Primary search provider.

#### `__init__()`

Tries to import and initialize:

```python
from ddgs import DDGS
self.ddgs = DDGS()
```

If package is missing, `self.ddgs = None`.

#### `search(query, max_results=5)`

Step by step:

1. Prints search query.
2. If `ddgs` is not available, returns empty list.
3. Calls:

   ```python
   self.ddgs.text(query, max_results=max_results, region='in-en')
   ```

4. Converts each raw DDG result to `SearchResult`.
5. Uses:
   - `href` or `url`
   - `title`
   - `body` or `description`
6. Skips results without URL/title.
7. Returns list of `SearchResult`.

#### `search_news()`

Uses:

```python
self.ddgs.news(query, max_results=max_results, region='in-en')
```

#### `search_with_location()`

Appends location to query.

### Class: `LLMBasedSearcher`

Older optional OpenAI web-search path.

Uses:

```python
self.client.responses.create(
    model="gpt-4o",
    tools=[{"type": "web_search_preview"}],
    input=query
)
```

Important limitation:

- It creates synthetic `SearchResult` with empty URL.
- Because of that, normal direct search now prefers DuckDuckGo real URLs.

### Class: `EnhancedSearcher`

Enhanced quality-scoring search provider.

#### DOMAIN_AUTHORITY

A dictionary that gives preferred domain scores:

```python
magicbricks.com: 85
99acres.com: 88
housing.com: 82
timesofindia.indiatimes.com: 90
economictimes.indiatimes.com: 92
wikipedia.org: 95
gov.in: 98
maharashtra.gov.in: 95
```

#### `search_with_quality(query, max_results=10)`

Step by step:

1. Searches DuckDuckGo with double requested results.
2. For every result:
   - detects content type
   - detects date presence
   - checks recency
   - calculates word count
   - calculates domain authority
   - calculates quality score
   - calculates relevance score
3. Combines score:

   ```python
   combined_score = relevance_score * 0.7 + quality_score * 0.3
   ```

4. Sorts by combined score.
5. Keeps results with score >= 30.

#### `_calculate_quality_score()`

Starts with base score 50.

Boosts:

- known authoritative domain
- title longer than 30 chars
- title contains official/government/rera/guideline/notification
- recent content
- snippet longer than 100 chars
- snippet contains price/rate/unit/sqft/bhk/rule/act
- PDF content

Penalizes:

- login
- sign up
- subscribe
- newsletter

#### `_calculate_relevance_score()`

Calculates keyword overlap between query and:

```text
title + snippet + URL
```

Adds exact phrase boost.

#### `_detect_content_type()`

Uses URL extension:

- `.pdf` -> `pdf`
- `.json` -> `json`
- otherwise `html`

## 6.6 `search_agent/source_discovery.py`

### Role

This is the main intelligence layer for normal API/default search.

It performs:

- query understanding
- LLM query planning
- domain disambiguation
- search query generation
- source ranking
- LLM reranking
- result filtering

### Constants And Rules

#### `STOP_WORDS`

Common words removed from entity extraction:

```text
a, an, and, are, as, at, be, by, can, do, for, ...
```

#### `DOMAIN_EXPANSIONS`

Hard-coded acronym/domain context.

Rules:

```python
fsi -> Floor Space Index
```

Context terms:

- building
- development control
- town planning
- sanctioned plan

Avoid terms:

- financial sanctions
- office of financial sanctions
- ofsi
- sanctions list

```python
udcpr -> Unified Development Control and Promotion Regulations Maharashtra
```

#### `PROPERTY_RATE_TERMS`

Used when query looks like property government-rate query:

- ready reckoner
- circle rate
- government valuation
- property rate
- guideline value
- IGR Maharashtra
- market value

#### `PROPERTY_RATE_AVOID_TERMS`

Penalized for property-rate queries:

- health.gov
- immunisation
- vaccine
- RSV
- disease
- medicine

#### `KNOWN_REAL_ESTATE_LOCATIONS`

Includes:

- Wakad
- Baner
- Hinjewadi
- Pune
- Kharadi
- Hadapsar
- Aundh
- Balewadi
- etc.

#### `GENERIC_OFF_TOPIC_TERMS`

Generic topic drift penalties:

- health terms
- financial sanctions terms
- jobs/recruitment terms

#### `MIN_RELEVANCE_SCORE`

```python
MIN_RELEVANCE_SCORE = 0.28
```

Results below this are filtered unless all results are weak.

### Dataclass: `QueryUnderstanding`

Fields:

| Field | Meaning |
|---|---|
| `original_query` | User query. |
| `intent` | explanation/latest/comparison/pricing/etc. |
| `key_entities` | Important terms and entities. |
| `rewritten_queries` | Search queries to run. |
| `positive_terms` | Terms that indicate relevance. |
| `avoid_terms` | Terms that indicate wrong topic. |
| `used_llm` | Whether LLM query planner was used. |

### Class: `SourceDiscovery`

#### `__init__()`

Accepts a searcher, usually `DuckDuckGoSearcher`.

If OpenAI key exists:

- initializes OpenAI client
- enables LLM planner and reranker

Tracks LLM token usage for search brain:

```python
input_tokens
output_tokens
total_tokens
total_cost
```

#### `understand_query(query)`

Step by step:

1. Tries `_understand_query_with_llm()`.
2. If LLM succeeds, returns LLM-generated `QueryUnderstanding`.
3. If LLM fails or is unavailable:
   - normalizes query
   - extracts entities
   - detects intent
   - detects domain context
   - builds rewritten queries
   - builds positive terms
   - returns rule-based `QueryUnderstanding`

#### `_understand_query_with_llm(query)`

Uses OpenAI Chat Completions.

The model is instructed to return JSON:

```json
{
  "intent": "...",
  "key_entities": [],
  "search_queries": [],
  "positive_terms": [],
  "avoid_terms": []
}
```

Rules in prompt:

- Resolve acronyms using context.
- In real estate/building context, FSI means Floor Space Index, not OFSI.
- Local property/government rates should use ready reckoner/circle rate/guideline value/IGR terms.
- Search queries should avoid unrelated results.
- Return JSON only.

#### `discover(query, max_results=5)`

Main source discovery method.

Step by step:

1. Resets token usage.
2. Gets `QueryUnderstanding`.
3. Runs up to 4 rewritten search queries.
4. For each search query:
   - calls DuckDuckGo
   - collects results
   - skips empty URLs
   - deduplicates by URL
   - runs `_rank_result()`
5. If LLM client exists:
   - calls `_rerank_with_llm()`
6. Sorts by final `relevance_score`.
7. Filters results below `MIN_RELEVANCE_SCORE`.
8. If all results are too weak:
   - returns empty list, or weak fallback only if top score >= 0.12.
9. Returns:

```python
{
  "understanding": {...},
  "results": [...],
  "token_usage": {...}
}
```

#### `_rank_result()`

Calculates relevance using:

- entity score
- topic overlap score
- query word overlap score
- phrase match score
- domain authority
- original search rank
- irrelevant result penalty

Formula:

```python
relevance_score =
    topic_score * 0.34
  + query_score * 0.24
  + entity_score * 0.18
  + phrase_score * 0.10
  + authority_score * 0.07
  + rank_score * 0.07
  - penalty
```

#### `_rerank_with_llm()`

Uses LLM to score top 12 candidates.

Prompt asks model to return:

```json
{
  "scores": [
    {"index": 1, "score": 0.0, "reason": "short reason"}
  ]
}
```

Rules:

- Score from 0 to 1.
- Wrong-topic results must be <= 0.15 even if official/government.
- Final relevance combines:

```python
final = llm_score * 0.72 + heuristic_score * 0.28
```

#### `_detect_domain_context()`

Adds context for:

- FSI
- UDCPR
- property-rate queries

#### `_is_property_rate_query()`

Returns true when:

- query contains government rate / ready reckoner / circle rate / property rate
- query contains known real-estate location

#### `_irrelevant_result_penalty()`

Penalizes:

- OFSI/financial sanctions for FSI queries
- vaccine/health pages for property-rate queries
- generic off-topic areas like jobs or health when not asked

## 6.7 `search_agent/analyzer.py`

### Role

Contains two analyzers:

- `LightweightAnalyzer`
- `EnhancedAnalyzer`

### Class: `LightweightAnalyzer`

Used by normal `main.py` and `api.py`.

#### `__init__()`

If `OPENAI_API_KEY` exists:

```python
self.client = OpenAI(api_key=config.OPENAI_API_KEY)
self.encoder = tiktoken.encoding_for_model("gpt-4o-mini")
```

Initializes cumulative token usage:

- input_tokens
- output_tokens
- total_cost
- query_count

#### `needs_analysis(query, results)`

Rules:

- If LLM client exists, always returns `True`.
- If no LLM:
  - simple queries with <= 3 results may skip LLM.
  - complex indicators trigger analysis:
    - compare
    - analysis
    - trend
    - vs
    - highest
    - best
    - why
    - how

#### `extract_keyword_insights(results)`

No LLM. Extracts:

- numbers
- dates
- locations
- key points

Rules:

- Looks only at top 5 results.
- Extracts numbers with units like lakh/crore/sqft/%.
- Detects selected Indian city names.
- Deduplicates output.

#### `analyze_results(query, results, keyword_insights)`

Step by step:

1. If no LLM, returns `_format_without_llm()`.
2. Builds context from top 5 results:
   - title
   - URL
   - relevance score
   - snippet
3. Gets query hint using `_get_query_hint()`.
4. Creates LLM prompt.
5. Calls OpenAI Chat Completions.
6. Tracks token usage.
7. Returns generated answer.

Prompt rules:

- Prefer sources with higher relevance scores.
- Ignore wrong-topic sources.
- If sources are not relevant enough, say so clearly.

#### `_get_query_hint(query)`

Hard-coded hints:

- `fsi` means Floor Space Index in building/real-estate/town-planning contexts.
- Do not interpret FSI as OFSI/financial sanctions unless user explicitly asks.
- `udcpr` means Unified Development Control and Promotion Regulations.

### Class: `EnhancedAnalyzer`

Used by enhanced CLI mode.

#### `extract_facts(results)`

Extracts from top 10 results:

- numbers
- dates
- locations

Each fact includes:

- source URL
- source title
- numbers
- dates
- locations
- snippet

#### `validate_consistency(facts)`

Rules:

- If fewer than 2 fact sources, confidence is 0.5.
- If multiple numeric values conflict, marks contradiction.
- Returns:

```python
is_consistent
confidence
contradictions
source_count
```

#### `generate_trust_score(result, query)`

Starts at 50.

Boosts:

- `.gov.in`
- `.nic.in`
- Wikipedia
- Times of India
- Economic Times
- Moneycontrol
- RERA/MahaRERA
- current year appears
- numbers appear
- rupee symbols appear
- sqft appears
- existing `quality_score`

Penalizes:

- sign up
- login
- newsletter
- subscribe

Outputs:

- score
- level: High/Medium/Low
- factors:
  - authority
  - recency
  - data richness

#### `analyze_with_confidence(query, results)`

Step by step:

1. If no results, returns low confidence response.
2. Extracts facts.
3. Validates consistency.
4. Scores sources.
5. Calculates average trust.
6. Combines trust with consistency:

   ```python
   overall_confidence = (avg_trust / 100) * consistency_confidence
   ```

7. Uses LLM answer if available.
8. Otherwise uses basic answer.
9. Returns:

```python
answer
confidence
confidence_level
sources_used
high_trust_sources
source_scores
consistency
key_findings
token_usage
```

#### `_generate_llm_answer()`

Prompt rules:

- Answer only from provided sources.
- Mention discrepancies.
- Include confidence level.
- Cite source numbers.
- Do not use unrelated sources.

## 6.8 `search_agent/processor.py`

### Role

Fetches and extracts readable content from source URLs.

Currently optional in normal flow. It runs only when:

```python
fetch_content=True
```

### Class: `ContentProcessor`

#### `__init__()`

Creates a `requests.Session`.

Adds browser-like user agent:

```text
Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36
```

Reads:

```python
config.MAX_CONTENT_LENGTH
```

#### `fetch_html(url, timeout=15)`

Rules:

- Uses `requests`.
- Retries up to 2 attempts using Tenacity.
- Raises for HTTP errors.
- Uses apparent encoding when available.
- Returns HTML string or `None`.

#### `extract_readable_content(html, url)`

Three extraction strategies:

1. Trafilatura:
   - used first when `EXTRACT_READABLE=true`
   - good for articles
2. Readability:
   - fallback if Trafilatura fails
3. BeautifulSoup:
   - removes script/style/nav/footer/header/aside/form
   - tries selectors:
     - main
     - article
     - `.content`
     - `#content`
     - `.main-content`
     - `.post-content`
   - falls back to all visible text

Then:

- cleans text
- limits length to `MAX_CONTENT_LENGTH`
- returns `(title, content)`

#### `extract_metadata(html, url)`

Extracts:

- Open Graph title
- Open Graph description
- Open Graph image
- Open Graph type
- meta description
- keywords
- author
- canonical URL
- published date

#### `process_batch(urls, delay=1.0)`

Processes URLs one by one.

For each URL:

1. Fetches HTML.
2. Extracts readable content.
3. Extracts metadata.
4. Appends result.
5. Sleeps between requests.

## 6.9 `search_agent/cache.py`

### Role

Persistent cache to reduce repeated search calls and token cost.

### Class: `SearchCache`

#### `__init__()`

Creates cache directory:

```python
Path(config.CACHE_DIR).mkdir(parents=True, exist_ok=True)
```

Uses DiskCache:

```python
Cache(str(self.cache_dir))
```

#### `_get_key(query, search_type="web")`

Builds key:

```python
f"{search_type}:{query.lower().strip()}"
```

Hashes with MD5.

#### `get(query, search_type="web")`

Step by step:

1. Builds cache key.
2. Checks key exists.
3. Reads cached entry.
4. Checks TTL.
5. Returns cached data if still valid.
6. Returns `None` otherwise.

#### `set(query, data, search_type="web")`

Stores:

- timestamp
- data
- query
- type

#### `clear(older_than=None)`

If `older_than` is passed:

- deletes only old entries.

If not:

- clears full cache.

#### `stats()`

Returns:

- total entries
- cache directory
- TTL seconds
- TTL hours

## 6.10 `search_agent/formatter.py`

### Role

Converts result dictionaries to human-readable formats.

No LLM is used in this file.

### Class: `ResponseFormatter`

#### `__init__()`

Defaults:

```python
max_snippets = 5
max_snippet_length = 300
```

#### `format_markdown()`

Outputs:

- title
- timestamp
- cache notice
- query discovery details
- analysis
- sources
- relevance score
- read-more links

#### `format_text()`

Plain terminal-friendly output.

Includes:

- query
- analysis
- discovery details
- source list

#### `format_json()`

Returns JSON string containing:

- query
- timestamp
- cache flag
- result count
- results
- discovery
- analysis
- token usage

Each result may include:

- source
- search query
- matched entities
- relevance score
- LLM relevance score
- LLM relevance reason

#### `format_streaming()`

Returns one JSON line for streaming-style responses.

#### `create_summary_table()`

Creates markdown table:

```markdown
| # | Title | Source |
```

## 6.11 `search_agent/utils.py`

Currently empty.

Possible future use:

- shared text cleaning
- URL normalization
- scoring utilities
- common constants

## 6.12 `tests/`

Files:

- `tests/test_searcher.py`
- `tests/test_analyzer.py`
- `tests/__init__.py`

Currently empty.

Recommended tests:

1. Query `what is sanctioned fsi` should produce Floor Space Index context.
2. Query `what is government rate in wakad` should prefer ready reckoner/property valuation.
3. Vaccine/health page should be rejected for property-rate query.
4. OFSI/financial sanctions should be rejected for FSI query.
5. `no_cache=true` should bypass cache in API.

## 7. Complete Normal Search Flow With Data Objects

Example query:

```text
what is government rate in wakad
```

### Step 1: API Receives Query

`api.py` receives:

```python
query = "what is government rate in wakad"
no_cache = True or False
```

Calls:

```python
agent.search(query, max_results, use_cache=not no_cache)
```

### Step 2: Cache Check

`main.py` creates:

```python
cache_query = "source-discovery-v5:what is government rate in wakad"
```

If found and valid:

- returns cached result
- no new search
- no new tokens

### Step 3: Source Discovery

`SourceDiscovery.discover()` starts.

If OpenAI key exists, LLM planner returns something like:

```json
{
  "intent": "pricing",
  "key_entities": ["government rate", "Wakad"],
  "search_queries": [
    "Wakad ready reckoner rate",
    "Wakad government valuation property rate",
    "Wakad IGR Maharashtra ready reckoner"
  ],
  "positive_terms": ["ready reckoner", "property valuation", "Wakad"],
  "avoid_terms": ["vaccine", "health", "RSV"]
}
```

If no LLM, rule-based property-rate logic creates similar query rewrites.

### Step 4: DuckDuckGo Search

Each rewritten query is searched through:

```python
DuckDuckGoSearcher.search()
```

The raw results become `SearchResult` objects.

### Step 5: Heuristic Ranking

Each result is scored using:

- topic overlap
- query overlap
- entity match
- phrase match
- authority score
- rank score
- penalties

Health/vaccine results get penalized for property-rate query.

### Step 6: LLM Reranking

If LLM is enabled:

- top 12 candidates are sent to OpenAI
- model scores each 0 to 1
- wrong-topic results must be <= 0.15
- final score combines LLM and heuristic score

### Step 7: Filtering

Results below `MIN_RELEVANCE_SCORE = 0.28` are filtered.

If every result is extremely weak, system returns no relevant results instead of forcing bad links.

### Step 8: Analysis

`LightweightAnalyzer` uses top results and asks LLM for answer.

The prompt includes:

- query
- query hint
- source titles
- URLs
- relevance scores
- snippets
- extracted locations/numbers/key points

### Step 9: Token Usage

Two token groups are returned:

`discovery_token_usage`:

- query planner
- reranker

`token_usage`:

- final answer generation

### Step 10: API Response

Returned to browser as JSON and rendered into HTML.

## 8. Enhanced CLI Flow

Command:

```powershell
py cli.py --enhanced "what is government rate in wakad"
```

### Step 1

`EnhancedSearchCLI.search()` calls:

```python
EnhancedSearcher.search_with_quality()
```

### Step 2

`EnhancedSearcher`:

- searches DuckDuckGo
- detects content type
- calculates domain authority
- calculates quality score
- calculates relevance score
- sorts by combined score

### Step 3

`EnhancedAnalyzer.analyze_with_confidence()`:

- extracts facts
- validates consistency
- scores trust
- calculates confidence
- generates answer

### Step 4

CLI prints:

- answer
- confidence level
- source trust score
- relevance
- quality
- domain authority
- source URL
- contradictions if found

## 9. Rules And Heuristics Summary

### Acronym Rules

| Term | Meaning |
|---|---|
| FSI | Floor Space Index in building/real estate context. |
| UDCPR | Unified Development Control and Promotion Regulations Maharashtra. |
| DCPR | Development Control Promotion Regulations. |
| OC | Occupancy Certificate. |
| CC | Completion Certificate. |

### Wrong Meaning Avoidance

For FSI:

- avoid OFSI
- avoid financial sanctions
- avoid sanctions list

For property government rates:

- avoid vaccine
- avoid health.gov
- avoid RSV
- avoid disease/medicine pages

### Relevance Rules

More relevant when:

- title/snippet contains query entities
- result includes positive terms
- exact phrase appears
- source is from strong domain and topic also matches

Less relevant when:

- official domain but wrong topic
- search result is about unrelated health/jobs/sanctions
- few query terms match
- only generic words match

### Quality Rules

Higher quality when:

- known trusted domain
- official/government/RERA/guideline/notification in title
- current year/latest appears
- snippet is detailed
- contains numbers/rates/sqft/rules
- PDF official document

Lower quality when:

- login/signup/subscribe/newsletter content
- weak snippet
- unknown domain with no data

## 10. LLM Prompts And Their Purpose

### Query Planner Prompt

File:

```text
search_agent/source_discovery.py
```

Purpose:

- Convert natural user query into structured search strategy.

Returns:

- intent
- key entities
- search queries
- positive terms
- avoid terms

### Reranker Prompt

File:

```text
search_agent/source_discovery.py
```

Purpose:

- Score result relevance from 0 to 1.
- Reject wrong-topic sources even if official.

### Answer Prompt

File:

```text
search_agent/analyzer.py
```

Purpose:

- Generate concise answer from ranked sources.
- Prefer high-relevance sources.
- Avoid guessing.

### Enhanced Answer Prompt

File:

```text
search_agent/analyzer.py
```

Class:

```python
EnhancedAnalyzer
```

Purpose:

- Answer with confidence level.
- Cite source numbers.
- Mention contradictions.

## 11. Token Tracking

### Search Brain Tokens

Source:

```python
SourceDiscovery.last_token_usage
```

Includes:

- query planner LLM call
- reranking LLM call

Displayed in API as:

```json
discovery_token_usage
```

### Answer Tokens

Source:

```python
LightweightAnalyzer.get_token_report()
```

`main.py` calculates per-query difference:

```python
token_after - token_before
```

Displayed in API as:

```json
token_usage
```

### Enhanced CLI Tokens

Source:

```python
EnhancedAnalyzer.get_token_report()
```

Shown in enhanced CLI output.

## 12. Cache Behavior

Cache key includes:

```python
SEARCH_CACHE_VERSION
```

Current:

```python
source-discovery-v5
```

Why this matters:

If relevance logic changes, old cached answers may be bad. Bump version to force fresh cache.

Use:

```text
no_cache=true
```

to bypass cache temporarily.

## 13. Security Notes

The API key must live only in `.env`.

`.gitignore` ignores:

```text
.env
.env.*
venv/
data/cache/
__pycache__/
*.db
*.db-wal
*.db-shm
```

Safe file:

```text
.env.example
```

This contains placeholders only.

## 14. Known Gaps Compared To Target Architecture

The requested target architecture includes:

```text
Parallel Fetching
Multi-Format Parsing HTML/PDF/JSON
Structured Data Extraction
Cross-Source Validation
Contradiction Detection
LLM Synthesis with citations
```

Current status:

| Feature | Status |
|---|---|
| Query understanding | Implemented, LLM + fallback. |
| Multiple search query variants | Implemented. |
| Multiple search engines | Partial, DuckDuckGo primary; OpenAI web-search path exists but is not preferred for real URLs. |
| Source quality scoring | Implemented in `EnhancedSearcher`. |
| Content type detection | Implemented in `EnhancedSearcher` by URL extension. |
| Parallel fetching | Not fully implemented; `process_batch()` is sequential. |
| HTML extraction | Implemented. |
| PDF parsing | Not implemented yet. |
| JSON parsing | Not implemented yet. |
| Deduplication | Implemented by URL in discovery and enhanced search. |
| Relevance filtering | Implemented. |
| Structured data extraction | Partial: regex facts in `EnhancedAnalyzer`. |
| Cross-source validation | Basic implementation in `EnhancedAnalyzer`. |
| Confidence score | Implemented in enhanced CLI. |
| Contradiction detection | Basic numeric contradiction detection. |
| Source attribution | URLs shown; enhanced answer asks for source numbers. |
| Citations in normal API answer | Partial; source URLs are separate, not inline citations. |

## 15. Recommended Next Development Steps

1. Add PDF parsing with `pypdf` or `pdfplumber`.
2. Add JSON endpoint parsing in `ContentProcessor`.
3. Add async parallel fetching with `aiohttp`.
4. Add source citations directly inside normal API answer.
5. Add tests for known bad cases:
   - FSI not OFSI
   - government rate in Wakad not vaccine result
   - irrelevant official domains filtered
6. Add a proper frontend template instead of inline HTML string.
7. Add a second search provider fallback such as SerpAPI or Google Custom Search if keys are available.
8. Add configurable domain preference rules per domain:
   - real estate
   - legal
   - government
   - medical
   - finance

## 16. Quick Developer Cheat Sheet

Run API:

```powershell
py api.py
```

Run direct CLI:

```powershell
py cli.py "what is sanctioned fsi"
```

Run enhanced CLI:

```powershell
py cli.py --enhanced "what is government rate in wakad"
```

Bypass cache:

```text
http://localhost:8000/api/search?query=what%20is%20government%20rate%20in%20wakad&no_cache=true
```

Main files to edit for relevance:

```text
search_agent/source_discovery.py
search_agent/searcher.py
search_agent/analyzer.py
```

Main files to edit for UI/API:

```text
api.py
main.py
search_agent/formatter.py
```

Main files to edit for CLI:

```text
cli.py
```

