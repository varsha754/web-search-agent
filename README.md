# 🔍 Web Search Agent — Complete System Documentation

An autonomous, LLM-powered web search agent that discovers sources, extracts content, cross-validates facts, and generates trusted answers with citations — streamed in real-time to the user.

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Directory Structure](#2-directory-structure)
3. [End-to-End Query Flow](#3-end-to-end-query-flow)
4. [File-by-File Documentation](#4-file-by-file-documentation)
5. [API Reference](#5-api-reference)
6. [Configuration](#6-configuration)
7. [Dependencies](#7-dependencies)
8. [Running the Project](#8-running-the-project)

---

## 1. Architecture Overview

```
User Query
    │
    ▼
┌──────────────────────────────────────────────────────────┐
│  FASTAPI SERVER (backend/main.py)                        │
│  Routes: /api/chat_stream, /api/search, /api/extract     │
└──────────────┬───────────────────────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────────────────────┐
│  AGENT (agents/UI_dashboard/main.py)                     │
│  DuckDuckGoSearchAgent.search()                          │
│                                                          │
│  Step 1: Cache Check (database/db.py)                    │
│      │                                                   │
│  Step 2: Source Discovery (tools/discovery.py)            │
│      ├── LLM query planning (OpenAI GPT-4o-mini)         │
│      ├── Multi-engine web search (tools/search.py)       │
│      │     ├── DuckDuckGo HTML scraping                  │
│      │     ├── Bing scraping                             │
│      │     ├── DDGS package                              │
│      │     └── SearXNG public instances                  │
│      ├── Result relevance scoring                        │
│      └── Source trust scoring                            │
│      │                                                   │
│  Step 3: Content Extraction (tools/browser.py)            │
│      ├── Trafilatura extraction                          │
│      ├── Mozilla Readability extraction                  │
│      ├── BeautifulSoup extraction                        │
│      ├── JSON-LD structured data                         │
│      └── Confidence scoring per source                   │
│      │                                                   │
│  Step 4: Cross-Validation (utils/validation.py)           │
│      ├── Extract claims from all sources                 │
│      ├── Find consensus claims                           │
│      └── Detect conflicting data                         │
│      │                                                   │
│  Step 5: LLM Analysis (agents/UI_dashboard/prompts.py)    │
│      ├── Build accuracy prompt with validation data      │
│      ├── Stream answer via OpenAI (SSE chunks)           │
│      └── Track token usage and cost                      │
│      │                                                   │
│  Step 6: Cache result (database/db.py)                    │
└──────────────────────────────────────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────────────────────┐
│  FRONTEND (frontend/app/page.tsx)                        │
│  Next.js UI with SSE streaming, Markdown rendering       │
└──────────────────────────────────────────────────────────┘
```

---

## 2. Directory Structure

### Backend

```
backend/
├── main.py                   # FastAPI app, routes, SSE streaming
├── schemas.py                # Pydantic schemas (placeholder)
├── requirements.txt          # Python dependencies
│
├── agents/
│   ├── UI_dashboard/
│   │   ├── main.py           # DuckDuckGoSearchAgent — orchestrator
│   │   ├── prompts.py        # LightweightAnalyzer, EnhancedAnalyzer
│   │   ├── tools.py          # ResponseFormatter (markdown/json/text)
│   │   └── README.md         # Agent documentation
│   ├── agent_two/            # Future agent (placeholder)
│   └── shared/
│       └── base_agent.py     # Shared base class (placeholder)
│
├── tools/
│   ├── search.py             # DuckDuckGoSearcher, EnhancedSearcher
│   ├── browser.py            # ContentProcessor (multi-strategy extraction)
│   ├── discovery.py          # SourceDiscovery, QueryUnderstanding
│   ├── rera_scraper.py       # RERA API integration (placeholder)
│   └── base_tool.py          # Abstract tool interface (placeholder)
│
├── database/
│   ├── db.py                 # SearchCache (diskcache-based)
│   ├── models.py             # DB models (placeholder)
│   └── migrations/
│
├── core/
│   ├── config.py             # Config class (env-based settings)
│   └── security.py           # Security utilities (placeholder)
│
├── utils/
│   ├── validation.py         # ExtractedData dataclass, AccuracyValidator
│   ├── timestamps.py         # Date extraction, relative time formatting
│   ├── logging.py            # (placeholder)
│   ├── auth.py               # (placeholder)
│   └── helpers.py            # (placeholder)
│
├── api/
│   ├── routes/               # Modular route files (placeholders)
│   ├── middleware/
│   └── schemas/
│
├── docs/                     # Internal documentation
└── tests/
    ├── test_analyzer.py
    └── test_searcher.py
```

### Frontend

```
frontend/
├── app/
│   ├── page.tsx              # Main search UI (SSE client)
│   ├── layout.tsx            # Root layout
│   ├── UI_creation/page.tsx  # Dashboard creation page
│   └── user_input/page.tsx   # User input page
├── components/               # Reusable UI components
│   ├── shared/
│   ├── agent-one/
│   └── agent-two/
├── lib/
│   └── api-client.ts         # API wrapper
├── hooks/                    # Custom React hooks
├── store/                    # State management
├── tools/                    # Frontend tool wrappers
├── types/
│   ├── agents.ts
│   └── api.ts
├── styles/
│   └── globals.css           # Global Tailwind styles
└── public/
```

---

## 3. End-to-End Query Flow

When a user types "ready reckoner rate Pune 2026" and hits Send:

### 3.1 Frontend → Backend (SSE Connection)

**File: `frontend/app/page.tsx`**

1. User submits query in the chat input
2. Frontend calls `GET /api/chat_stream?query=ready+reckoner+rate+Pune+2026`
3. Opens an SSE (Server-Sent Events) stream via `fetch()` + `ReadableStream`
4. Listens for events: `status` (progress), `chunk` (streamed text), `done` (final result), `error`

**File: `backend/main.py`**

5. The `/api/chat_stream` endpoint creates an `asyncio.Queue`
6. Defines two callbacks: `status_callback(msg)` and `stream_callback(msg)`
7. Spawns a **background thread** running `agent.search()` (because OpenAI SDK is synchronous)
8. The async generator yields SSE events from the queue as `data: {json}\n\n`

### 3.2 Cache Check

**File: `agents/UI_dashboard/main.py` → `DuckDuckGoSearchAgent.search()`**

9. Builds cache key: `"source-discovery-v6-top10:ready reckoner rate Pune 2026"`
10. Calls `SearchCache.get()` — if cache hit within TTL (1 hour), returns immediately
11. On cache miss, proceeds to Step 2

**File: `database/db.py` → `SearchCache`**

- Uses `diskcache.Cache` for persistent file-based caching
- Cache key = MD5 hash of `"web:{query}"`
- TTL configurable via `CACHE_TTL` env var (default: 3600s)

### 3.3 Source Discovery

**File: `tools/discovery.py` → `SourceDiscovery.discover()`**

12. **Query Understanding (LLM):** Sends query to GPT-4o-mini with a JSON schema prompt. Returns:
    - `intent`: "pricing"
    - `key_entities`: ["ready reckoner", "rate", "Pune", "2026"]
    - `search_queries`: ["ready reckoner rate Pune 2026", "annual statement of rates Pune", ...]
    - `avoid_terms`: ["vaccine", "immunisation"]
13. **Real Estate Detection:** `RealEstateIntentDetector.is_real_estate_query()` checks for property keywords → returns `True`
14. **Property Rate Detection:** `_is_property_rate_query()` matches "ready reckoner" → generates 8 specialized queries like "ready reckoner rate Pune 2026", "circle rate Pune residential land rate"
15. **Multi-Query Search:** For each of 6 rewritten queries:

**File: `tools/search.py` → `DuckDuckGoSearcher.search()`**

16. Searches the exact query across 4 providers in cascade:
    - **DuckDuckGo HTML** (`_search_duckduckgo_html`): Scrapes `html.duckduckgo.com`, parses `.result` blocks, extracts real URLs from `uddg=` redirect parameters
    - **Bing** (`_search_bing`): Scrapes `bing.com/search`, parses `.b_algo` blocks, decodes base64 redirect URLs
    - **DDGS Package** (`_search_ddgs_package`): Uses the `duckduckgo-search` Python package as third fallback
    - **SearXNG** (`_search_searxng`): Queries random public SearXNG instances via JSON API
17. Results are **deduplicated** by normalized URL (strip www, trailing slash)
18. Returns `List[SearchResult]` with url, title, snippet, source, rank

**Back in `discovery.py`:**

19. **Source Validation:** For real estate queries, `is_valid_real_estate_source()` filters out:
    - Tourism sites (TripAdvisor, MakeMyTrip, etc.)
    - Results with < 2 real estate indicators
    - For rate queries: results that look like project listings instead of rate data
20. **Relevance Scoring:** `_rank_result()` calculates topic overlap between query terms and result text. Rate queries get a +0.35 boost if the result looks like rate data.
21. **Trust Scoring:** `_calculate_source_trust()` scores by domain signals: `.gov.in` +0.30, `.edu` +0.20, short domains +0.05
22. **Domain Filtering:** `filter_relevant_sources()` removes tourism, health, and off-topic content
23. **LLM Reranking:** (currently simplified) Sends top 10 candidates to LLM for reranking
24. **Final Selection:** Sort by `trust_score * 0.4 + relevance_score * 0.6`, filter by minimum relevance 0.28, take top `max_results`

### 3.4 Content Extraction

**File: `agents/UI_dashboard/main.py`**

25. Takes top 10 URLs from discovery results
26. Calls `ContentProcessor.process_batch(urls)`

**File: `tools/browser.py` → `ContentProcessor`**

27. For each URL, calls `fetch_html()` (with retry via tenacity: 2 attempts, exponential backoff)
28. Calls `extract_with_confidence(url, html, query)` which tries **3 extraction methods**:

| Method | Library | Quality Score | Best For |
|---|---|---|---|
| Trafilatura | `trafilatura` | 0.85 | News articles, blogs |
| Readability | `readability-lxml` | 0.80 | Long-form content |
| BeautifulSoup | `beautifulsoup4` | 0.75 | Fallback for any HTML |

29. Each method's result is scored: `final_score = quality * 0.6 + relevance * 0.4`
30. Best extraction is selected. Content is capped at 10,000 characters.
31. **Structured data extraction**: Parses `<script type="application/ld+json">` for JSON-LD (Article, NewsArticle, Product schemas). If `articleBody` found, it overrides the extracted content.
32. **Metadata extraction** from content:
    - `_extract_key_facts()`: Sentences with numbers + query keyword matches
    - `_extract_numbers()`: Currency (₹ lakh/crore), area (sqft), BHK, percentages
    - `_extract_dates()`: ISO dates, `DD Mon YYYY` patterns
    - `_extract_locations()`: Known Indian city/area names
    - `_extract_entities()`: Capitalized phrases before "project", "builder", "developer"
33. **Confidence scoring** (`_calculate_confidence`): Sum of extraction method score (max 30) + source trust (max 25) + word count bonus (max 20) + structured data bonus (10) + key facts bonus (max 15)
34. **Source trust** (`_infer_source_trust`): Government domains, educational domains, structured data presence, content length, query keyword overlap
35. **Publish date extraction** (`utils/timestamps.py`): Tries 4 strategies — Open Graph meta tags → `<time>` elements → JSON-LD `datePublished` → regex patterns in HTML
36. Returns list of dicts with: url, title, content, published_date, time_ago, confidence_score, source_trust, extracted_data

### 3.5 Cross-Source Validation

**File: `utils/validation.py` → `AccuracyValidator.cross_validate()`**

37. Extracts **claims** from each source's `ExtractedData`:
    - Numerical claims (values + context)
    - Date claims
    - Key fact claims
38. **Consensus detection**: Groups claims by `type:value` key. Claims appearing in 2+ sources are "validated"
39. **Conflict detection**: Finds numerical claims with same context but different values
40. **Accuracy score calculation**:
    - `avg_confidence * 0.4` (source quality)
    - `consensus_score` (max 45 for validated claims)
    - `diversity_score` (unique domains, max 20)
    - `base_floor` of 30 if 2+ sources
41. Returns: accuracy_score, validated_claims, conflicting_claims, recommendation

### 3.6 LLM Analysis & Streaming

**File: `agents/UI_dashboard/prompts.py` → `LightweightAnalyzer.generate_trusted_answer()`**

42. Builds a detailed prompt with:
    - User query
    - Up to 10 source contexts (title, URL, trust score, content up to 5000 chars each)
    - Cross-validation data (verified claims, contradictions)
    - Format instructions (for real estate: table format; for general: executive summary + findings)
43. Calls OpenAI `chat.completions.create()` with `stream=True`:
    - Model: `gpt-4o-mini` (configurable)
    - Temperature: 0.2 (factual)
    - Max tokens: `MAX_TOKENS * 2` (default: 1000)
44. Each streamed chunk is sent to `stream_callback(content)` → pushed to the asyncio Queue → yielded as SSE `data: {"type":"chunk","content":"..."}`
45. **Token tracking**: Input tokens estimated as `len(prompt) // 4`, output tokens as `len(full_text) // 4`
46. **Real estate post-processing**: `validate_real_estate_content()` checks if tourism content leaked into the response and replaces it with a correction message

### 3.7 Response Assembly & Caching

**File: `agents/UI_dashboard/main.py`**

47. Assembles final output dict:
    ```python
    {
        "query": "ready reckoner rate Pune 2026",
        "success": True,
        "discovery": { intent, key_entities, rewritten_queries, ... },
        "discovery_token_usage": { input_tokens, output_tokens, total_cost },
        "results_count": 10,
        "results": [ { url, title, snippet, content, source_trust, ... } ],
        "analysis": "## Executive Summary\n...",
        "accuracy": { accuracy_score, confidence_level, recommendation },
        "token_usage": { input_tokens, output_tokens, total_cost },
        "timestamp": "2026-05-08T12:00:00"
    }
    ```
48. Converts any dataclass objects to dicts for JSON serialization
49. Caches result via `SearchCache.set()`
50. Sends final SSE event: `data: {"type":"done","result":{...}}`

### 3.8 Frontend Rendering

**File: `frontend/app/page.tsx`**

51. On receiving `chunk` events: Appends text to `fullText`, renders with `marked.parse()` (Markdown → HTML)
52. On receiving `done` event:
    - Hides blinking cursor and status spinner
    - Renders sources list with clickable URLs
    - Shows token usage badge (input/output tokens, cost)

---

## 4. File-by-File Documentation

### `backend/main.py` — FastAPI Server
- **Purpose**: HTTP entry point. Serves the built-in HTML chat UI and exposes API endpoints.
- **Key class**: `SearchRequest` (Pydantic model: query, max_results, format)
- **Routes**:
  - `GET /` — Inline HTML/CSS/JS chat interface with SSE streaming
  - `GET /api/search` — Synchronous JSON search
  - `GET /api/extract` — Extract data from a specific URL
  - `GET /api/stats` — Agent statistics
  - `GET /health` — Health check (LLM status, cache status)
  - `GET /api/chat_stream` — SSE streaming endpoint (primary)
- **SSE mechanism**: Uses `threading.Thread` to run synchronous agent in background, `asyncio.Queue` to bridge thread→async, yields `StreamingResponse`

### `backend/agents/UI_dashboard/main.py` — Agent Orchestrator
- **Purpose**: Central orchestrator that wires together all components
- **Key class**: `DuckDuckGoSearchAgent`
- **Components initialized**: `DuckDuckGoSearcher`, `SourceDiscovery`, `ContentProcessor`, `LightweightAnalyzer`, `ResponseFormatter`, `SearchCache`, `AccuracyValidator`
- **`search()` method**: The main pipeline — cache check → discovery → content extraction → validation → LLM analysis → cache store
- **`extract_from_url()`**: Single-URL extraction for the `/api/extract` endpoint
- **Stats tracking**: queries, cache_hits, cache_misses, total_tokens, total_cost

### `backend/agents/UI_dashboard/prompts.py` — LLM Analyzers
- **Purpose**: All LLM prompt engineering and response generation
- **Key classes**:
  - `LightweightAnalyzer`: Primary analyzer used in production. Supports streaming. Builds context-aware prompts (news vs real estate vs general). Tracks token usage.
  - `EnhancedAnalyzer`: Extended analyzer with trust scoring, fact extraction, consistency validation. Used by CLI/enhanced mode.
- **Prompt types**: News aggregator prompt, real estate project prompt, construction status prompt, general fact-checking prompt
- **Streaming**: `_get_llm_answer_with_confidence_stream()` yields chunks via callback

### `backend/agents/UI_dashboard/tools.py` — Response Formatter
- **Purpose**: Format results into user-friendly output (0 token usage)
- **Key class**: `ResponseFormatter`
- **Formats**: Markdown (with clickable links), plain text, JSON, streaming JSON
- **`create_summary_table()`**: Quick overview table of results

### `backend/tools/discovery.py` — Query Understanding & Source Discovery
- **Purpose**: First stage of the pipeline. Understands what the user wants, builds optimized queries, searches the web, and ranks results.
- **Key classes**:
  - `SourceDiscovery`: Main discovery engine
  - `QueryUnderstanding`: Dataclass holding intent, entities, rewritten queries
  - `RealEstateIntentDetector`: Domain-specific intent classifier
- **LLM usage**: Query planning (intent detection, entity extraction, query rewriting). Token-efficient: ~450 tokens per query.
- **Specialized handling**: Property rate queries get 8 targeted search queries, result boosting for rate-related content, and filtering of project listings

### `backend/tools/search.py` — Web Search Engine
- **Purpose**: Multi-provider web search with no API keys required
- **Key classes**:
  - `DuckDuckGoSearcher`: Primary searcher. Cascades through 4 providers: DuckDuckGo HTML → Bing → DDGS package → SearXNG
  - `EnhancedSearcher`: Wrapper adding quality scoring, recency filtering, date-based sorting, and parallel multi-query search
  - `LLMBasedSearcher`: Optional GPT-4o powered search (returns synthetic insights, not real URLs)
  - `SearchResult`: Dataclass with url, title, snippet, quality metrics
- **Deduplication**: Normalizes URLs (strip www, trailing slash) to prevent duplicates across providers
- **Rate limit handling**: Exponential backoff with jitter on 403/202 errors

### `backend/tools/browser.py` — Content Extraction
- **Purpose**: Fetches web pages and extracts clean content with confidence scoring
- **Key class**: `ContentProcessor`
- **3-strategy extraction**: Trafilatura → Readability → BeautifulSoup (best score wins)
- **Structured data**: Extracts JSON-LD schemas (Article, NewsArticle, Product, RealEstateListing)
- **Metadata extraction**: Numbers, dates, locations, entities, key facts — all with regex patterns
- **Trust scoring**: `_infer_source_trust()` scores based on domain type, content quality, structured data presence
- **Batch processing**: `process_batch()` processes multiple URLs with configurable delay between requests

### `backend/tools/rera_scraper.py` — RERA Integration
- **Purpose**: Placeholder for MahaRERA API integration
- **Status**: Returns empty list (RERA site uses CAPTCHAs). Falls back to web scraping.

### `backend/database/db.py` — Cache System
- **Purpose**: Persistent disk-based caching to reduce API calls and LLM usage
- **Key class**: `SearchCache`
- **Storage**: `diskcache.Cache` (SQLite-backed file cache)
- **Key generation**: MD5 hash of `"web:{query}"`
- **TTL**: Configurable (default 3600s / 1 hour)
- **Token savings**: 90%+ for repeated queries

### `backend/core/config.py` — Configuration
- **Purpose**: Centralized environment-based configuration
- **Key class**: `Config`
- **Settings groups**: DuckDuckGo (region, timeout), LLM (model, tokens, API key), content processing (max length), cache (TTL, directory), rate limiting (delay, retries), response format, API server (host, port)
- **LLM auto-detection**: `USE_LLM = bool(OPENAI_API_KEY)` — system works without OpenAI key (falls back to keyword extraction)

### `backend/utils/validation.py` — Accuracy Validation
- **Purpose**: Cross-source fact validation and accuracy scoring
- **Key classes**:
  - `ExtractedData`: Dataclass holding all extracted content and metadata
  - `AccuracyValidator`: Validates data across multiple sources
- **Claim extraction**: Numbers, dates, key facts — each tagged with source URL and trust score
- **Consensus**: Claims appearing in 2+ sources are marked as validated
- **Conflict detection**: Finds numerical claims with same context but different values
- **Accuracy formula**: `(avg_confidence * 0.4) + consensus + diversity + base_floor`

### `backend/utils/timestamps.py` — Date Utilities
- **Purpose**: Extract publication dates from HTML and format as relative time strings
- **`extract_publish_date()`**: 4-strategy extraction: OG meta tags → `<time>` elements → JSON-LD → regex
- **`parse_date()`**: Tries 12 date formats (ISO, US, EU, natural language)
- **`get_time_ago()`**: Converts datetime to "3 hours ago", "2 days ago", etc.

### `frontend/app/page.tsx` — Main Search UI
- **Purpose**: Chat-style search interface with real-time streaming
- **SSE client**: Connects to `/api/chat_stream`, processes `status`/`chunk`/`done`/`error` events
- **Markdown rendering**: Uses `marked` library for rich formatting
- **Token display**: Shows input/output tokens and cost after each query

### `backend/main.py` (inline HTML) — Built-in Chat UI
- **Purpose**: Self-contained chat interface served at `/` (no frontend build needed)
- **Features**: Dark theme, Markdown rendering via `marked.js`, blinking cursor during streaming, source links, token usage badges

---

## 5. API Reference

### `GET /api/chat_stream`
Primary endpoint. Streams results via Server-Sent Events.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `query` | string | required | Search query (min 1 char) |
| `no_cache` | bool | false | Skip cache |
| `debug` | bool | false | Include LLM payloads in response |

**SSE Event Types:**
- `{"type":"status","content":"Finding sources..."}` — Progress update
- `{"type":"chunk","content":"## Summary\n..."}` — Streamed answer text
- `{"type":"done","result":{...}}` — Final complete result object
- `{"type":"error","content":"..."}` — Error message

### `GET /api/search`
Synchronous search. Returns full JSON result.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `query` | string | required | Search query |
| `max_results` | int | 10 | Maximum results |
| `no_cache` | bool | false | Skip cache |

### `GET /api/extract`
Extract data from a specific URL.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `url` | string | required | URL to extract from |
| `query` | string | required | What to extract |

### `GET /api/stats`
Returns agent statistics (queries, cache hits, token usage).

### `GET /health`
Returns `{"status":"healthy","llm_enabled":true,"cache_enabled":true}`

---

## 6. Configuration

All settings are in `.env` (copy from `.env.example`):

```env
# Search engine
DDG_MAX_RESULTS=10
DDG_TIMEOUT=10
DDG_REGION=wt-wt              # wt-wt = worldwide

# LLM (optional — system works without it)
OPENAI_API_KEY=sk-...          # Leave empty for keyword-only mode
LLM_MODEL=gpt-4o-mini         # Cost-efficient model
MAX_TOKENS=500                 # Per-response token limit

# Content extraction
MAX_CONTENT_LENGTH=5000        # Max chars extracted per page
EXTRACT_READABLE=true

# Caching
CACHE_ENABLED=true
CACHE_TTL=3600                 # 1 hour
CACHE_DIR=data/cache

# Rate limiting
REQUEST_DELAY=1.0              # Seconds between requests
MAX_RETRIES=3

# Response
DEFAULT_FORMAT=markdown
MAX_RESULTS_IN_RESPONSE=10

# Server
API_HOST=0.0.0.0
API_PORT=8000
```

---

## 7. Dependencies

### Backend (Python)
| Package | Purpose |
|---|---|
| `fastapi` + `uvicorn` | Web server and async HTTP |
| `openai` | LLM API (GPT-4o-mini) |
| `tiktoken` | Token counting |
| `duckduckgo-search` | DuckDuckGo search API |
| `requests` | HTTP client for scraping |
| `beautifulsoup4` + `lxml` | HTML parsing |
| `trafilatura` | Article content extraction |
| `readability-lxml` | Mozilla Readability algorithm |
| `diskcache` | Persistent file-based cache |
| `tenacity` | Retry logic with exponential backoff |
| `python-dotenv` | Environment variable loading |
| `pydantic` | Data validation and schemas |

### Frontend (Node.js)
| Package | Purpose |
|---|---|
| `next` (v16) | React framework (App Router) |
| `react` (v19) | UI library |
| `marked` | Markdown → HTML rendering |
| `tailwindcss` (v4) | Utility-first CSS |

---

## 8. Running the Project

### Backend
```bash
cd web_search_agent
pip install -r backend/requirements.txt
cp .env.example .env           # Add your OPENAI_API_KEY
uvicorn main:app --reload --app-dir backend
# → http://localhost:8000 (built-in chat UI)
```

### Frontend (Next.js)
```bash
cd frontend
npm install
npm run dev
# → http://localhost:3000 (Next.js UI)
```

### Both together
- Backend runs on port 8000
- Frontend runs on port 3000
- CORS is configured to allow `localhost:3000` → `localhost:8000`
