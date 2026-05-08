# UI Dashboard Agent

## Overview
The `DuckDuckGoSearchAgent` is the primary search agent that orchestrates the full search-and-analyze pipeline for the web UI.

## Files

| File | Purpose |
|---|---|
| `main.py` | Agent entry point — `DuckDuckGoSearchAgent` class with `search()`, `extract_from_url()` |
| `prompts.py` | LLM prompts and analyzers — `LightweightAnalyzer`, `EnhancedAnalyzer` |
| `tools.py` | Response formatting — `ResponseFormatter` (markdown, JSON, text, streaming) |

## Pipeline Flow
1. **Cache check** → return cached result if available
2. **Source Discovery** → `tools/discovery.py` understands query intent and finds relevant URLs
3. **Content Extraction** → `tools/browser.py` fetches and extracts content from top URLs
4. **Cross-Validation** → `utils/validation.py` validates facts across multiple sources
5. **LLM Analysis** → `prompts.py` generates a trusted answer with citations
6. **Token Tracking** → aggregates input/output token usage and cost
