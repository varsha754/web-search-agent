# Web Search Agent Documentation

## 1. Project Overview

This project is a Python-based web search agent. It accepts a user query, understands the intent, searches the web, ranks relevant sources, optionally uses an LLM to improve search accuracy, and returns an answer with source links and token usage.

The project can run in three ways:

- Command-line interactive app: `py main.py`
- Enhanced CLI search: `py cli.py "your query"`
- Localhost web UI/API: `py api.py`, then open `http://localhost:8000`

The current agent is designed to behave more like a search engine:

1. Understand the query.
2. Rewrite the query into better search queries.
3. Search multiple relevant URLs.
4. Rank and filter results.
5. Use an LLM to produce a concise answer when configured.
6. Show token usage and source links.

## 2. Main Workflow

For a normal API search, the flow is:

```text
User query
  -> api.py / main.py
  -> SourceDiscovery
       -> LLM query planner, if OPENAI_API_KEY is available
       -> DuckDuckGo search
       -> heuristic ranking
       -> LLM reranking, if OPENAI_API_KEY is available
  -> LightweightAnalyzer
       -> LLM answer generation, if OPENAI_API_KEY is available
       -> fallback plain formatting if no LLM
  -> ResponseFormatter / API JSON / localhost UI
```

## 3. Tools And Libraries Used

### Search Tools

| Tool | Package | Used In | Purpose |
|---|---|---|---|
| DuckDuckGo search | `ddgs` / `duckduckgo-search` | `search_agent/searcher.py` | Gets real search result URLs, titles, and snippets. |
| OpenAI web search preview | `openai` | `LLMBasedSearcher` in `searcher.py` | Older/optional LLM search path. It may return synthetic answers without real URLs, so direct CLI was changed to prefer DuckDuckGo real links. |

### LLM Tools

| Model / Tool | Used In | Purpose |
|---|---|---|
| `gpt-4o-mini` by default | `source_discovery.py`, `analyzer.py`, `cli.py` | Query planning, result reranking, and answer generation. |
| `gpt-4o` | `LLMBasedSearcher` in `searcher.py` | Optional OpenAI Responses API web-search path. |
| `tiktoken` | `analyzer.py` | Token encoding setup and token-related support. |

The model used by most LLM calls is configured through:

```env
LLM_MODEL=gpt-4o-mini
```

If `OPENAI_API_KEY` is not set, the system still searches with DuckDuckGo, but LLM planning, reranking, and answer generation are disabled.

### Web/API Tools

| Tool | Package | Used In | Purpose |
|---|---|---|---|
| FastAPI | `fastapi` | `api.py` | Provides localhost web UI and JSON API endpoints. |
| Uvicorn | `uvicorn` | `api.py` | Runs the FastAPI server. |
| Pydantic | `pydantic` | `api.py` | Defines request models. |

### Content Extraction Tools

| Tool | Package | Used In | Purpose |
|---|---|---|---|
| Requests | `requests` | `processor.py` | Fetches web page HTML. |
| BeautifulSoup | `beautifulsoup4` | `processor.py` | Parses and cleans HTML. |
| Trafilatura | `trafilatura` | `processor.py` | Extracts readable article/content text. |
| Readability | `readability-lxml` | `processor.py` | Fallback extraction for readable content. |
| Newspaper | `newspaper3k` | `processor.py` | Imported for article extraction support. |
| Tenacity | `tenacity` | `processor.py` | Retries failed HTTP fetches. |

### Cache And Utility Tools

| Tool | Package | Used In | Purpose |
|---|---|---|---|
| DiskCache | `diskcache` | `cache.py` | Persistent local cache for search results. |
| python-dotenv | `python-dotenv` | `config.py` | Loads `.env` values. |
| Redis | `redis` | `requirements.txt` | Listed dependency, not currently used in active source code. |
| Rich | `rich` | `requirements.txt` | Listed dependency, not currently used in active source code. |
| prometheus-client | `prometheus-client` | `requirements.txt` | Listed dependency, not currently used in active source code. |
| structlog | `structlog` | `requirements.txt` | Listed dependency, not currently used in active source code. |

## 4. File-By-File Documentation

### `config.py`

Central configuration file. Loads environment variables using `python-dotenv`.

Important settings:

| Setting | Default | Purpose |
|---|---|---|
| `OPENAI_API_KEY` | empty | Enables LLM features when present. |
| `USE_LLM` | `bool(OPENAI_API_KEY)` | True if OpenAI key exists. |
| `LLM_MODEL` | `gpt-4o-mini` | Main model for planning/reranking/analysis. |
| `MAX_TOKENS` | `500` | Max answer tokens for LLM answer generation. |
| `CACHE_ENABLED` | `true` | Enables local result cache. |
| `CACHE_TTL` | `3600` | Cache lifetime in seconds. |
| `CACHE_DIR` | `data/cache` | Local cache folder. |
| `MAX_RESULTS_IN_RESPONSE` | `5` | Number of results returned to user. |
| `API_HOST` | `0.0.0.0` | FastAPI host. |
| `API_PORT` | `8000` | FastAPI port. |

### `main.py`

Main orchestrator. Defines `DuckDuckGoSearchAgent`.

Responsibilities:

- Initializes all core components:
  - `DuckDuckGoSearcher`
  - `SourceDiscovery`
  - `ContentProcessor`
  - `LightweightAnalyzer`
  - `ResponseFormatter`
  - `SearchCache`
- Checks cache before searching.
- Runs query understanding and source discovery.
- Optionally fetches page content.
- Runs LLM answer generation through `LightweightAnalyzer`.
- Tracks per-query token usage.
- Caches results.
- Provides interactive terminal mode with `main()`.

Important method:

```python
search(query, max_results=5, fetch_content=False, use_cache=True)
```

Returns a dictionary containing:

- `query`
- `success`
- `discovery`
- `discovery_token_usage`
- `results_count`
- `results`
- `analysis`
- `token_usage`
- `timestamp`

`SEARCH_CACHE_VERSION` is used to avoid returning old cached results after relevance logic changes.

### `api.py`

FastAPI web server and localhost UI.

Endpoints:

| Endpoint | Method | Purpose |
|---|---|---|
| `/` | GET | Simple browser UI. |
| `/api/search` | GET | JSON search API. |
| `/api/stats` | GET | Returns agent stats. |
| `/health` | GET | Health check. |

Example:

```text
http://localhost:8000/api/search?query=what%20is%20government%20rate%20in%20wakad&no_cache=true
```

Query parameters:

| Parameter | Purpose |
|---|---|
| `query` | User search query. |
| `max_results` | Optional number of results. |
| `no_cache=true` | Forces fresh search and fresh token usage. |

The localhost UI displays:

- Analysis
- Answer token usage
- Search brain token usage
- Query understanding
- Source discovery queries
- Relevance score
- LLM relevance score when available
- Source URLs

### `cli.py`

Enhanced command-line interface.

Main features:

- Direct search mode.
- Smart search mode for real estate-style queries.
- News search mode.
- Interactive mode.
- Token usage display.

Common commands:

```powershell
py cli.py "latest AI model updates"
py cli.py "what is sanctioned fsi"
py cli.py "what is government rate in wakad"
py cli.py --smart "best investment areas in Pune"
py cli.py --news "real estate news"
py cli.py --enhanced "what is government rate in wakad"
py cli.py -i
```

Important classes:

| Class | Purpose |
|---|---|
| `DirectSearchAgent` | Direct source-first search with optional LLM answer. |
| `QueryOptimizer` | LLM-based real-estate query intent optimizer. |
| `SmartSearchCLI` | Smart CLI workflow using query expansion. |
| `EnhancedSearchCLI` | Enhanced workflow with relevance, quality, trust, and confidence scores. |

### `search_agent/source_discovery.py`

This is the most important relevance component.

Responsibilities:

1. Understand the user query.
2. Extract key entities.
3. Detect intent.
4. Expand ambiguous terms.
5. Generate better search queries.
6. Search multiple variants.
7. Rank results heuristically.
8. Rerank with LLM when available.
9. Filter weak or irrelevant results.

Important class:

```python
SourceDiscovery
```

Important methods:

| Method | Purpose |
|---|---|
| `understand_query()` | Builds a `QueryUnderstanding` object. |
| `discover()` | Runs full discovery and ranking pipeline. |
| `_understand_query_with_llm()` | Uses LLM as query planner. |
| `_rerank_with_llm()` | Uses LLM to score result relevance. |
| `_rank_result()` | Heuristic score combining topic overlap, entity match, authority, and rank. |
| `_irrelevant_result_penalty()` | Penalizes wrong-topic results. |

`QueryUnderstanding` contains:

- `original_query`
- `intent`
- `key_entities`
- `rewritten_queries`
- `positive_terms`
- `avoid_terms`
- `used_llm`

Domain-specific logic currently includes:

| Case | Behavior |
|---|---|
| `fsi` | Expands to `Floor Space Index`; avoids `OFSI` / financial sanctions. |
| `udcpr` | Expands to Maharashtra building regulation context. |
| `government rate in Wakad` | Interprets as ready reckoner / circle rate / property valuation. |
| health/vaccine pages | Penalized for property-rate queries. |

Scoring considers:

- Topic overlap
- Query-term overlap
- Entity match
- Phrase match
- Domain authority
- Search result rank
- Off-topic penalties
- Optional LLM relevance score

### `search_agent/searcher.py`

Contains low-level search providers.

Classes:

| Class | Purpose |
|---|---|
| `SearchResult` | Dataclass for result URL, title, snippet, source, rank, content, relevance. |
| `DuckDuckGoSearcher` | Searches DuckDuckGo using `ddgs`. |
| `LLMBasedSearcher` | Optional OpenAI web-search-preview path. |
| `EnhancedSearcher` | Adds source quality scoring, content type detection, domain authority, recency flags, and multi-query deduplication. |

`DuckDuckGoSearcher` is the main active source provider because it returns real clickable URLs.

Important methods:

```python
search(query, max_results=5)
search_news(query, max_results=5)
search_with_location(query, location, max_results=5)
```

### `search_agent/analyzer.py`

Generates the final answer from ranked search results.

Class:

```python
LightweightAnalyzer
```

Responsibilities:

- Decides whether LLM analysis is needed.
- Extracts basic keyword insights without LLM.
- Creates a prompt using result titles, snippets, URLs, and relevance scores.
- Uses OpenAI chat completions for answer generation.
- Tracks token usage and estimated cost.
- Falls back to plain formatted search results when LLM is unavailable.

Important methods:

| Method | Purpose |
|---|---|
| `needs_analysis()` | Returns whether to use LLM. |
| `extract_keyword_insights()` | Extracts numbers, locations, key points. |
| `analyze_results()` | Produces final answer. |
| `_get_query_hint()` | Adds context hints for terms like FSI/UDCPR. |
| `get_token_report()` | Returns cumulative token usage. |

Additional class:

| Class | Purpose |
|---|---|
| `EnhancedAnalyzer` | Extracts facts, checks cross-source consistency, scores source trust, and generates confidence-aware answers. |

### `search_agent/processor.py`

Fetches and extracts readable content from URLs.

Class:

```python
ContentProcessor
```

Responsibilities:

- Fetch HTML with `requests`.
- Retry failed fetches using `tenacity`.
- Extract readable content with:
  - Trafilatura
  - Readability
  - BeautifulSoup fallback
- Extract metadata like:
  - Open Graph title/description/image/type
  - meta description
  - canonical URL
  - published date
- Clean noisy text.

Currently used when `fetch_content=True` is passed to `agent.search()`.

### `search_agent/cache.py`

Persistent disk cache.

Class:

```python
SearchCache
```

Responsibilities:

- Store search results in `data/cache`.
- Avoid repeated search and LLM cost for same query.
- Respect TTL from `CACHE_TTL`.
- Show cache stats.
- Clear old cache entries.

Important note:

Cached requests do not use new LLM tokens. In the localhost UI, cached results show:

```text
Cached result
No new LLM tokens were used for this request.
```

Use `no_cache=true` to force fresh token usage.

### `search_agent/formatter.py`

Formats output into:

- Markdown
- Plain text
- JSON
- Streaming JSON lines

Class:

```python
ResponseFormatter
```

Includes discovery metadata and relevance scores in formatted output.

### `search_agent/utils.py`

Currently empty / unused.

### `tests/`

Test files exist:

- `tests/test_searcher.py`
- `tests/test_analyzer.py`

They are currently empty in this workspace.

## 5. LLM Usage Details

The project uses OpenAI in three separate ways.

### 5.1 Query Planning

File:

```text
search_agent/source_discovery.py
```

Function:

```python
_understand_query_with_llm()
```

Purpose:

- Understand query intent.
- Resolve acronyms.
- Generate better search queries.
- Produce positive and avoid terms.

Output example:

```json
{
  "intent": "pricing",
  "key_entities": ["Wakad", "government rate", "ready reckoner"],
  "search_queries": [
    "Wakad ready reckoner rate",
    "Wakad government valuation property rate",
    "Wakad IGR Maharashtra ready reckoner"
  ],
  "positive_terms": ["ready reckoner", "property valuation", "Wakad"],
  "avoid_terms": ["vaccine", "health", "RSV"]
}
```

### 5.2 Result Reranking

File:

```text
search_agent/source_discovery.py
```

Function:

```python
_rerank_with_llm()
```

Purpose:

- Looks at the top candidate links.
- Scores each result from `0` to `1`.
- Gives wrong-topic results low scores.
- Combines LLM score with heuristic score.

Displayed in UI as:

```text
LLM relevance: 0.87
```

### 5.3 Answer Generation

File:

```text
search_agent/analyzer.py
```

Function:

```python
analyze_results()
```

Purpose:

- Uses ranked sources.
- Includes relevance score and URL in the prompt.
- Produces the final concise answer.
- Avoids using irrelevant sources when possible.

## 6. Token Usage

The project tracks two types of token usage.

### Search Brain Token Usage

From `SourceDiscovery`:

- LLM query planning
- LLM result reranking

Returned as:

```json
"discovery_token_usage": {
  "input_tokens": 123,
  "output_tokens": 45,
  "total_tokens": 168,
  "total_cost": 0.000045
}
```

### Answer Token Usage

From `LightweightAnalyzer`:

- Final answer generation

Returned as:

```json
"token_usage": {
  "input_tokens": 382,
  "output_tokens": 152,
  "total_tokens": 534,
  "total_cost": 0.000148
}
```

The localhost UI displays both.

## 7. Environment Setup

Install dependencies:

```powershell
cd D:\vs_project_search_engine\web_search_agent
py -m pip install -r requirements.txt
```

Create `.env`:

```env
OPENAI_API_KEY=your_api_key_here
LLM_MODEL=gpt-4o-mini
CACHE_ENABLED=true
CACHE_TTL=3600
MAX_RESULTS_IN_RESPONSE=5
API_HOST=0.0.0.0
API_PORT=8000
```

Without `OPENAI_API_KEY`, the project still runs with DuckDuckGo search, but LLM planning, reranking, and answer generation are disabled.

## 8. How To Run

### Run Localhost UI

```powershell
py api.py
```

Open:

```text
http://localhost:8000
```

Fresh non-cached API call:

```text
http://localhost:8000/api/search?query=what%20is%20government%20rate%20in%20wakad&no_cache=true
```

### Run Main Interactive CLI

```powershell
py main.py
```

### Run Enhanced CLI

```powershell
py cli.py "what is sanctioned fsi"
py cli.py "what is government rate in wakad"
py cli.py "latest AI model updates"
py cli.py --enhanced "what is government rate in wakad"
```

## 9. Example API Response Shape

```json
{
  "query": "what is government rate in wakad",
  "success": true,
  "discovery": {
    "original_query": "what is government rate in wakad",
    "intent": "pricing",
    "key_entities": ["government rate", "Wakad"],
    "rewritten_queries": [
      "Wakad ready reckoner rate",
      "Wakad government valuation property rate"
    ],
    "positive_terms": ["ready reckoner", "property valuation", "Wakad"],
    "avoid_terms": ["vaccine", "health"],
    "used_llm": true
  },
  "discovery_token_usage": {
    "input_tokens": 300,
    "output_tokens": 100,
    "total_tokens": 400,
    "total_cost": 0.000105
  },
  "results_count": 5,
  "results": [
    {
      "url": "https://...",
      "title": "Wakad Ready Reckoner Rate...",
      "snippet": "...",
      "rank": 1,
      "source": "duckduckgo",
      "search_query": "Wakad ready reckoner rate",
      "matched_entities": ["wakad"],
      "relevance_score": 0.84,
      "llm_relevance_score": 0.9,
      "llm_relevance_reason": "Directly about ready reckoner rates in Wakad."
    }
  ],
  "analysis": "Final answer...",
  "token_usage": {
    "input_tokens": 382,
    "output_tokens": 152,
    "total_tokens": 534,
    "total_cost": 0.000148
  }
}
```

## 10. Known Limitations

- DuckDuckGo results can still occasionally return unrelated pages.
- LLM reranking improves relevance but costs extra tokens.
- If source snippets are weak, the final answer may still be limited.
- `processor.py` can fetch page content, but the default API path currently relies mainly on search snippets unless `fetch_content=True` is used internally.
- Some files contain garbled emoji characters due to encoding issues in earlier prints; functionality is mostly unaffected, but cleanup would improve readability.
- `redis`, `rich`, `prometheus-client`, and `structlog` are listed but not actively used.

## 11. Recommended Next Improvements

1. Add tests for:
   - FSI means Floor Space Index.
   - Government rate in Wakad means ready reckoner/property valuation.
   - Health/vaccine result is rejected for property-rate queries.
2. Add optional full-page fetching for top 3 results before answer generation.
3. Add a clearer UI with sections for:
   - Query planning
   - Source ranking
   - Final answer
   - Token usage
4. Add source citations inside the final answer.
5. Add a domain allow/prefer list for real-estate/legal/government queries.
6. Store LLM reranking reasons in the UI for debugging relevance.
