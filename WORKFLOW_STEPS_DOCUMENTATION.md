# Workflow Steps Documentation

This document maps the requested seven-step workflow diagram to the current codebase.

Important note: the current project is a DuckDuckGo web search agent, not a PostgreSQL analytics agent. Because of that, Step 1 and Step 2 exist in the code, but they are implemented as search-query understanding and search-query planning. Steps 3 to 7 are either represented by equivalent search-agent stages or are not implemented in the exact SQL/analytics form shown in the diagram.

## Current End-To-End Flow

```text
User query
  -> DuckDuckGoSearchAgent.search()
  -> SourceDiscovery.discover()
       -> understand intent and entities
       -> generate planned search queries
       -> select DuckDuckGo search tool
       -> run searches
       -> rank/filter/rerank sources
  -> ContentProcessor.process_batch()
       -> fetch and extract content from top URLs
  -> LightweightAnalyzer.generate_trusted_answer()
       -> validate source data
       -> generate final answer with confidence metadata
  -> ResponseFormatter / API JSON / frontend
```

Main orchestrator:

```text
backend/agents/UI_dashboard/main.py
DuckDuckGoSearchAgent.search()
```

## Step 1 - Intent And Entity Extraction

Diagram description:

```text
LLM -> structured JSON: intent, metric, group_by, geo, filters, time_range
```

Current implementation:

```text
backend/tools/discovery.py
SourceDiscovery.understand_query()
```

This is the closest matching Step 1 in the current code. It returns a `QueryUnderstanding` object, not the exact analytics JSON from the diagram.

Current structured output:

```python
@dataclass
class QueryUnderstanding:
    original_query: str
    intent: str
    key_entities: List[str]
    rewritten_queries: List[str]
    positive_terms: List[str]
    avoid_terms: List[str]
    used_llm: bool = False
    is_real_estate: bool = False
```

Important files and functions:

| Purpose | File | Function / Class |
|---|---|---|
| Main Step 1 entry point | `backend/tools/discovery.py` | `SourceDiscovery.understand_query()` |
| LLM-based intent/entity extraction | `backend/tools/discovery.py` | `_understand_query_with_llm()` |
| Fallback entity extraction | `backend/tools/discovery.py` | `_extract_key_entities()` |
| Fallback intent detection | `backend/tools/discovery.py` | `_detect_intent()` |
| Domain context detection | `backend/tools/discovery.py` | `_detect_domain_context()` |
| Step 1 output schema | `backend/tools/discovery.py` | `QueryUnderstanding` |

LLM prompt output shape currently requested:

```json
{
  "intent": "explanation|latest|comparison|pricing|recommendation|research|how_to",
  "key_entities": ["specific terms, acronyms, locations, products, laws, people"],
  "synonyms": ["technical synonyms, alternative terms, expanded acronyms"],
  "search_queries": ["3-5 optimized queries for latest articles and official docs"],
  "positive_terms": ["technical terms that indicate relevance"],
  "avoid_terms": ["terms that indicate wrong context or unrelated topic"]
}
```

Difference from diagram:

| Diagram Field | Current Equivalent |
|---|---|
| `intent` | `intent` |
| `geo` | usually part of `key_entities`; no separate `geo` field |
| `filters` | partly represented by `avoid_terms`, `positive_terms`, real-estate filters |
| `time_range` | inferred for latest/news queries; no separate `time_range` field |
| `metric` | not implemented |
| `group_by` | not implemented |

## Step 2 - Planning Agent

Diagram description:

```text
LLM -> ordered step list: geo_filter -> compute_metric -> group_by -> trend
```

Current implementation:

There is no separate `PlanningAgent` class or `planning_agent.py` file. The current planning logic is inside `SourceDiscovery`.

Important files and functions:

| Purpose | File | Function |
|---|---|---|
| LLM creates planned search queries | `backend/tools/discovery.py` | `_understand_query_with_llm()` |
| Fallback deterministic planning | `backend/tools/discovery.py` | `_build_search_queries()` |
| Adds positive relevance terms | `backend/tools/discovery.py` | `_build_positive_terms()` |
| Deduplicates planned queries | `backend/tools/discovery.py` | `_dedupe_queries()` |
| Orchestrates planning and discovery | `backend/tools/discovery.py` | `discover()` |

Current planning output:

```text
rewritten_queries
positive_terms
avoid_terms
```

Example conceptual output:

```json
{
  "intent": "latest",
  "key_entities": ["RERA", "Pune"],
  "rewritten_queries": [
    "RERA Pune latest",
    "RERA Pune news",
    "RERA Pune official source"
  ],
  "positive_terms": ["RERA", "Pune", "latest"],
  "avoid_terms": []
}
```

Difference from diagram:

The diagram expects an analytics execution plan such as:

```text
geo_filter -> compute_metric -> group_by -> trend
```

The current code creates a search plan:

```text
optimized search query 1 -> optimized search query 2 -> optimized search query 3
```

## Step 3 - Tool Selection Agent

Diagram description:

```text
Map each plan step -> filter tool or compute tool dynamically
```

Current implementation:

There is no separate dynamic tool-selection agent. Tool use is hardcoded by the orchestrator.

Closest implementation:

| Purpose | File | Function / Class |
|---|---|---|
| Search tool initialized | `backend/agents/UI_dashboard/main.py` | `DuckDuckGoSearchAgent.__init__()` |
| Source discovery uses searcher | `backend/tools/discovery.py` | `SourceDiscovery.__init__()` |
| DuckDuckGo search execution | `backend/tools/search.py` | `DuckDuckGoSearcher`, `EnhancedSearcher` |
| Browser/content extraction tool | `backend/tools/browser.py` | `ContentProcessor` |

Current behavior:

```text
SourceDiscovery -> DuckDuckGo searcher
DuckDuckGoSearchAgent -> ContentProcessor
DuckDuckGoSearchAgent -> LightweightAnalyzer
DuckDuckGoSearchAgent -> ResponseFormatter
```

## Step 4 - Query Builder

Diagram description:

```text
Schema-aware SQL generation with validation + self-healing retry loop
```

Current implementation:

SQL query building is not implemented. The closest equivalent is search-query generation.

Closest implementation:

| Purpose | File | Function |
|---|---|---|
| Build search queries with time filter | `backend/tools/discovery.py` | `build_search_query()` |
| Build rewritten search queries | `backend/tools/discovery.py` | `_build_search_queries()` |
| LLM-generated search query strings | `backend/tools/discovery.py` | `_understand_query_with_llm()` |

Current query builder output:

```text
DuckDuckGo search strings
```

Not currently implemented:

```text
SQL generation
schema-aware validation
self-healing SQL repair
database query plan
```

## Step 5 - Execution Engine

Diagram description:

```text
PostgreSQL execute -> on error: send back to LLM -> fix -> retry (max 3)
```

Current implementation:

PostgreSQL execution is not implemented. The equivalent execution layer is web-search execution plus content fetching.

Closest implementation:

| Purpose | File | Function |
|---|---|---|
| Execute planned search queries | `backend/tools/discovery.py` | `discover()` |
| Search backend | `backend/tools/search.py` | `search()`, `search_with_quality()` |
| Fetch HTML | `backend/tools/browser.py` | `fetch_html()` |
| Batch content extraction | `backend/tools/browser.py` | `process_batch()` |

Current retry behavior:

| Area | Current Behavior |
|---|---|
| Search results | Falls back to relaxed filters for some real-estate/news queries |
| Content fetching | Uses retry decorator for HTML fetching |
| SQL self-healing | Not implemented |

## Step 6 - Post-Processing Layer

Diagram description:

```text
Pandas: trend %, YoY, weighted avg, outlier detection, formatting
```

Current implementation:

Analytics post-processing with Pandas is not implemented. The current post-processing validates extracted source data and prepares answer metadata.

Closest implementation:

| Purpose | File | Function |
|---|---|---|
| Merge fetched content into result objects | `backend/agents/UI_dashboard/main.py` | `DuckDuckGoSearchAgent.search()` |
| Extract facts, numbers, dates, locations, entities | `backend/tools/browser.py` | `extract_with_confidence()` |
| Cross-source validation | `backend/utils/validation.py` | `AccuracyValidator.cross_validate()` |
| Confidence metadata | `backend/agents/UI_dashboard/prompts.py` | `generate_trusted_answer()` |

Current post-processing output:

```text
accuracy_score
confidence_level
recommendation
validated_claims
source_trust
extracted_data
```

Not currently implemented:

```text
Pandas trend calculation
YoY calculation
weighted average
outlier detection
metric aggregation
```

## Step 7 - Response Formatter Agent

Diagram description:

```text
LLM -> markdown table + plain-language insight + data confidence score
```

Current implementation:

Step 7 is split between LLM answer generation and non-LLM formatting.

Important files and functions:

| Purpose | File | Function / Class |
|---|---|---|
| LLM final answer generation | `backend/agents/UI_dashboard/prompts.py` | `LightweightAnalyzer.generate_trusted_answer()` |
| Builds answer prompt from sources and validation | `backend/agents/UI_dashboard/prompts.py` | `_build_accuracy_prompt()` |
| Markdown/text/JSON formatting | `backend/agents/UI_dashboard/tools.py` | `ResponseFormatter` |
| API response assembly | `backend/agents/UI_dashboard/main.py` | `DuckDuckGoSearchAgent.search()` |

Current final response contains:

```text
query
success
discovery
results_count
results
analysis
accuracy
timestamp
token_usage
```

## Where The Current Workflow Starts

Primary runtime path:

```text
backend/main.py
  -> creates FastAPI app
  -> imports DuckDuckGoSearchAgent

backend/agents/UI_dashboard/main.py
  -> DuckDuckGoSearchAgent.search()
```

Main call inside the search method:

```python
discovery = self.discovery.discover(query, max_results)
```

That single call triggers the current Step 1 and Step 2 behavior.

## Summary Mapping

| Diagram Step | Diagram Name | Current Status | Main File |
|---|---|---|---|
| Step 1 | Intent + entity extraction | Implemented, but with search-focused fields | `backend/tools/discovery.py` |
| Step 2 | Planning agent | Partially implemented as search-query planning | `backend/tools/discovery.py` |
| Step 3 | Tool selection agent | Not separate; tools are hardcoded | `backend/agents/UI_dashboard/main.py`, `backend/tools/discovery.py` |
| Step 4 | Query builder | Search-query builder exists; SQL builder does not | `backend/tools/discovery.py` |
| Step 5 | Execution engine | Web search/content execution exists; PostgreSQL execution does not | `backend/tools/search.py`, `backend/tools/browser.py` |
| Step 6 | Post-processing layer | Source validation exists; Pandas analytics do not | `backend/utils/validation.py`, `backend/agents/UI_dashboard/prompts.py` |
| Step 7 | Response formatter agent | Implemented through LLM answer + formatter | `backend/agents/UI_dashboard/prompts.py`, `backend/agents/UI_dashboard/tools.py` |

## Recommended File Structure If You Want The Diagram Exactly

To implement the diagram exactly, the project should add a dedicated analytics-agent layer like this:

```text
backend/
  agents/
    analytics_agent/
      __init__.py
      main.py
      intent_extractor.py
      planner.py
      tool_selector.py
      query_builder.py
      execution_engine.py
      post_processor.py
      response_formatter.py
      schemas.py
```

Recommended responsibility per file:

| File | Responsibility |
|---|---|
| `intent_extractor.py` | Convert user query to structured JSON: intent, metric, group_by, geo, filters, time_range |
| `planner.py` | Convert structured intent into ordered execution steps |
| `tool_selector.py` | Map each plan step to a filter, compute, aggregate, or trend tool |
| `query_builder.py` | Generate schema-aware SQL and validate it before execution |
| `execution_engine.py` | Execute PostgreSQL queries and retry repaired SQL on errors |
| `post_processor.py` | Use Pandas for trend, YoY, weighted averages, outliers, and formatting-ready tables |
| `response_formatter.py` | Generate markdown table, plain-language explanation, and confidence score |
| `schemas.py` | Shared Pydantic models for structured outputs between steps |

## Key Takeaway

In the current repo, Step 1 and Step 2 are implemented together in `backend/tools/discovery.py`.

The exact SQL analytics workflow from the diagram is not yet implemented. The project currently performs a web-search workflow:

```text
intent/entity extraction -> search-query planning -> DuckDuckGo execution -> source ranking -> content extraction -> LLM answer -> response formatting
```

