"""
Query understanding and source discovery.

This is the first step of the search workflow:
1. Understand user intent and key entities.
2. Build a few focused search queries.
3. Visit multiple relevant result URLs and rank them by relevance.
"""

import re
import json
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional
from urllib.parse import urlparse

from config import config
from search_agent.searcher import DuckDuckGoSearcher, SearchResult


STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "can", "do", "for",
    "from", "give", "have", "how", "i", "in", "is", "it", "me", "most",
    "of", "on", "or", "regarding", "search", "show", "that", "the", "this",
    "to", "want", "what", "whatever", "when", "where", "which", "will",
    "with", "you",
}


DOMAIN_EXPANSIONS = {
    "fsi": {
        "expanded": "Floor Space Index",
        "context_terms": ["building", "development control", "town planning", "sanctioned plan"],
        "avoid_terms": ["financial sanctions", "office of financial sanctions", "ofsi", "sanctions list"],
    },
    "udcpr": {
        "expanded": "Unified Development Control and Promotion Regulations Maharashtra",
        "context_terms": ["building rules", "development control", "Maharashtra"],
        "avoid_terms": [],
    },
}


PROPERTY_RATE_TERMS = [
    "ready reckoner",
    "circle rate",
    "government valuation",
    "property rate",
    "guideline value",
    "igr maharashtra",
    "market value",
]

PROPERTY_RATE_AVOID_TERMS = [
    "health.gov",
    "immunisation",
    "immunization",
    "vaccine",
    "vaccines",
    "respiratory-syncytial-virus",
    "rsv",
    "disease",
    "medicine",
]

KNOWN_REAL_ESTATE_LOCATIONS = {
    "wakad", "baner", "hinjewadi", "kharadi", "wagholi", "nibm", "punawale",
    "kondhwa", "pune", "mumbai", "thane", "balewadi", "aundh", "hadapsar",
    "magarpatta", "kothrud", "pimple", "saudagar", "mahalunge", "ravet",
}

GENERIC_OFF_TOPIC_TERMS = {
    "health": ["vaccine", "vaccines", "immunisation", "immunization", "disease", "medicine", "hospital"],
    "finance_sanctions": ["sanctions list", "financial sanctions", "ofsi", "asset freeze"],
    "jobs": ["hiring", "salary", "vacancy", "recruitment"],
}

MIN_RELEVANCE_SCORE = 0.28


@dataclass
class QueryUnderstanding:
    original_query: str
    intent: str
    key_entities: List[str]
    rewritten_queries: List[str]
    positive_terms: List[str]
    avoid_terms: List[str]
    used_llm: bool = False

    def to_dict(self) -> Dict:
        return asdict(self)


class SourceDiscovery:
    """Find and rank relevant sources for any user query."""

    def __init__(self, searcher: DuckDuckGoSearcher = None):
        self.searcher = searcher or DuckDuckGoSearcher()
        self.client = None
        self.last_token_usage = {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "total_cost": 0.0,
        }
        if config.USE_LLM and config.OPENAI_API_KEY:
            try:
                from openai import OpenAI
                self.client = OpenAI(api_key=config.OPENAI_API_KEY)
            except Exception as e:
                print(f"   ⚠️ LLM query planner not available: {e}")

    def understand_query(self, query: str) -> QueryUnderstanding:
        llm_understanding = self._understand_query_with_llm(query)
        if llm_understanding:
            return llm_understanding

        cleaned = self._normalize_query(query)
        entities = self._extract_key_entities(cleaned)
        intent = self._detect_intent(cleaned)
        domain_context = self._detect_domain_context(cleaned, entities)
        rewritten_queries = self._build_search_queries(cleaned, intent, entities, domain_context)
        positive_terms = self._build_positive_terms(cleaned, entities, domain_context)

        return QueryUnderstanding(
            original_query=query,
            intent=intent,
            key_entities=entities,
            rewritten_queries=rewritten_queries,
            positive_terms=positive_terms,
            avoid_terms=domain_context.get("avoid_terms", []),
            used_llm=False,
        )

    def discover(self, query: str, max_results: int = 5) -> Dict:
        self._reset_token_usage()
        understanding = self.understand_query(query)
        candidates = []
        seen_urls = set()

        # Search multiple variants so broad or vague questions still discover good sources.
        for search_query in understanding.rewritten_queries[:4]:
            results = self.searcher.search(search_query, max_results=max(max_results * 2, 8))
            for result in results:
                if not result.url or result.url in seen_urls:
                    continue
                seen_urls.add(result.url)
                candidates.append(self._rank_result(result, understanding, search_query))

        if self.client and candidates:
            candidates = self._rerank_with_llm(query, understanding, candidates)

        ranked = sorted(
            candidates,
            key=lambda item: (item["relevance_score"], -item["rank"]),
            reverse=True,
        )

        filtered = [item for item in ranked if item["relevance_score"] >= MIN_RELEVANCE_SCORE]
        if filtered:
            selected = filtered[:max_results]
        elif ranked and ranked[0]["relevance_score"] >= 0.12:
            selected = ranked[:max_results]
        else:
            selected = []

        return {
            "understanding": understanding.to_dict(),
            "results": selected,
            "token_usage": self.last_token_usage,
        }

    def _reset_token_usage(self):
        self.last_token_usage = {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "total_cost": 0.0,
        }

    def _add_token_usage(self, response):
        usage = getattr(response, "usage", None)
        if not usage:
            return
        input_tokens = getattr(usage, "prompt_tokens", 0) or 0
        output_tokens = getattr(usage, "completion_tokens", 0) or 0
        input_cost = input_tokens * 0.00000015
        output_cost = output_tokens * 0.0000006
        self.last_token_usage["input_tokens"] += input_tokens
        self.last_token_usage["output_tokens"] += output_tokens
        self.last_token_usage["total_tokens"] += input_tokens + output_tokens
        self.last_token_usage["total_cost"] = round(
            self.last_token_usage["total_cost"] + input_cost + output_cost,
            6,
        )

    def _understand_query_with_llm(self, query: str) -> Optional[QueryUnderstanding]:
        if not self.client:
            return None

        prompt = f"""You are a search query planner like Google search intent understanding.
Analyze the user query and produce only valid JSON.

User query: {query}

Return this JSON shape:
{{
  "intent": "explanation|latest|comparison|pricing|recommendation|research|how_to",
  "key_entities": ["specific terms, acronyms, locations, products, laws, people"],
  "search_queries": ["3 to 5 highly relevant web search queries"],
  "positive_terms": ["terms that must indicate relevance"],
  "avoid_terms": ["terms that indicate a wrong meaning or unrelated topic"]
}}

Rules:
- Resolve acronyms using query context. Example: in real estate/building context, FSI means Floor Space Index, not OFSI.
- If the user asks about local property/government rates, prefer ready reckoner, circle rate, guideline value, IGR, property valuation terms.
- Search queries should be specific enough to avoid unrelated results.
- Do not include explanations outside JSON."""

        try:
            response = self.client.chat.completions.create(
                model=config.LLM_MODEL,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=450,
                temperature=0.1,
            )
            self._add_token_usage(response)
            data = self._parse_json(response.choices[0].message.content)
            if not data:
                return None

            cleaned = self._normalize_query(query)
            entities = self._clean_term_list(data.get("key_entities", [])) or self._extract_key_entities(cleaned)
            intent = str(data.get("intent") or self._detect_intent(cleaned)).strip().lower()
            rewritten_queries = self._dedupe_queries(data.get("search_queries", []))[:5]
            if not rewritten_queries:
                domain_context = self._detect_domain_context(cleaned, entities)
                rewritten_queries = self._build_search_queries(cleaned, intent, entities, domain_context)

            positive_terms = self._clean_term_list(data.get("positive_terms", []))
            positive_terms = self._dedupe_terms(positive_terms + entities + self._important_terms(cleaned))
            avoid_terms = self._clean_term_list(data.get("avoid_terms", []))

            return QueryUnderstanding(
                original_query=query,
                intent=intent,
                key_entities=entities,
                rewritten_queries=rewritten_queries,
                positive_terms=positive_terms,
                avoid_terms=avoid_terms,
                used_llm=True,
            )
        except Exception as e:
            print(f"   ⚠️ LLM query planning failed: {e}")
            return None

    def _rerank_with_llm(self, query: str, understanding: QueryUnderstanding, candidates: List[Dict]) -> List[Dict]:
        shortlist = candidates[:12]
        source_lines = []
        for i, item in enumerate(shortlist, 1):
            source_lines.append(
                f"{i}. title={item.get('title', '')[:140]} | url={item.get('url', '')} | snippet={item.get('snippet', '')[:240]}"
            )

        prompt = f"""You are a search result reranker.
User query: {query}
Intent: {understanding.intent}
Key entities: {', '.join(understanding.key_entities)}
Positive relevance terms: {', '.join(understanding.positive_terms)}
Avoid terms/wrong meanings: {', '.join(understanding.avoid_terms)}

Search results:
{chr(10).join(source_lines)}

Return only valid JSON:
{{
  "scores": [
    {{"index": 1, "score": 0.0, "reason": "short reason"}}
  ]
}}

Score each result from 0 to 1 for whether it directly answers the query.
Give unrelated or wrong-meaning results <= 0.15 even if they are from government or official domains."""

        try:
            response = self.client.chat.completions.create(
                model=config.LLM_MODEL,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=700,
                temperature=0.0,
            )
            self._add_token_usage(response)
            data = self._parse_json(response.choices[0].message.content)
            scores = data.get("scores", []) if data else []
            score_by_index = {}
            reason_by_index = {}
            for item in scores:
                try:
                    index = int(item.get("index"))
                    score_by_index[index] = max(0.0, min(1.0, float(item.get("score", 0))))
                    reason_by_index[index] = str(item.get("reason", ""))[:160]
                except Exception:
                    continue

            reranked = []
            for i, item in enumerate(shortlist, 1):
                if i in score_by_index:
                    heuristic_score = item.get("relevance_score", 0.0)
                    llm_score = score_by_index[i]
                    item = {
                        **item,
                        "llm_relevance_score": round(llm_score, 4),
                        "llm_relevance_reason": reason_by_index.get(i, ""),
                        "relevance_score": round((llm_score * 0.72) + (heuristic_score * 0.28), 4),
                    }
                reranked.append(item)

            remaining = candidates[len(shortlist):]
            return reranked + remaining
        except Exception as e:
            print(f"   ⚠️ LLM reranking failed: {e}")
            return candidates

    def _parse_json(self, text: str) -> Optional[Dict]:
        try:
            return json.loads(text)
        except Exception:
            pass
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                return json.loads(text[start:end])
            except Exception:
                return None
        return None

    def _clean_term_list(self, values) -> List[str]:
        if not isinstance(values, list):
            return []
        cleaned = []
        for value in values:
            value = self._normalize_query(str(value))
            if value and value.lower() not in [item.lower() for item in cleaned]:
                cleaned.append(value)
        return cleaned[:12]

    def _normalize_query(self, query: str) -> str:
        return re.sub(r"\s+", " ", query).strip()

    def _extract_key_entities(self, query: str) -> List[str]:
        words = re.findall(r"[A-Za-z0-9][A-Za-z0-9.+#-]*", query)
        entities = []

        for word in words:
            lower = word.lower()
            if lower in STOP_WORDS or len(lower) < 2:
                continue
            if lower not in [item.lower() for item in entities]:
                entities.append(word)

        # Preserve quoted phrases as strong entities.
        for phrase in re.findall(r'"([^"]+)"|' + r"'([^']+)'", query):
            value = next((part for part in phrase if part), "").strip()
            if value and value.lower() not in [item.lower() for item in entities]:
                entities.insert(0, value)

        return entities[:8]

    def _detect_domain_context(self, query: str, entities: List[str]) -> Dict:
        query_lower = query.lower()
        entity_lowers = {entity.lower() for entity in entities}
        context = {
            "expansions": [],
            "context_terms": [],
            "avoid_terms": [],
            "domain": None,
        }

        for acronym, details in DOMAIN_EXPANSIONS.items():
            if acronym in entity_lowers or re.search(rf"\b{re.escape(acronym)}\b", query_lower):
                context["expansions"].append(details["expanded"])
                context["context_terms"].extend(details["context_terms"])
                context["avoid_terms"].extend(details["avoid_terms"])

        if self._is_property_rate_query(query_lower, entity_lowers):
            context["domain"] = "property_rate"
            context["context_terms"].extend(PROPERTY_RATE_TERMS)
            context["avoid_terms"].extend(PROPERTY_RATE_AVOID_TERMS)

        return context

    def _is_property_rate_query(self, query_lower: str, entity_lowers: set) -> bool:
        has_rate_phrase = (
            "government rate" in query_lower
            or "govt rate" in query_lower
            or "ready reckoner" in query_lower
            or "circle rate" in query_lower
            or "property rate" in query_lower
        )
        has_location = bool(entity_lowers.intersection(KNOWN_REAL_ESTATE_LOCATIONS))
        return has_rate_phrase and has_location

    def _detect_intent(self, query: str) -> str:
        query_lower = query.lower()
        intent_keywords = {
            "latest": ["latest", "today", "current", "recent", "news", "update"],
            "comparison": ["compare", "vs", "versus", "difference", "better"],
            "explanation": ["what is", "explain", "meaning", "definition", "how"],
            "pricing": ["price", "cost", "rate", "fees", "charges"],
            "recommendation": ["best", "top", "most relevant", "recommend"],
        }

        for intent, keywords in intent_keywords.items():
            if any(keyword in query_lower for keyword in keywords):
                return intent
        return "research"

    def _build_search_queries(
        self,
        query: str,
        intent: str,
        entities: List[str],
        domain_context: Dict = None,
    ) -> List[str]:
        domain_context = domain_context or {}
        entity_query = " ".join(entities) if entities else query
        expanded_terms = " ".join(domain_context.get("expansions", []))
        context_terms = " ".join(domain_context.get("context_terms", [])[:3])
        domain_query = self._normalize_query(f"{query} {expanded_terms} {context_terms}")

        queries = [domain_query if expanded_terms else query]

        if domain_context.get("domain") == "property_rate":
            location_terms = [entity for entity in entities if entity.lower() in KNOWN_REAL_ESTATE_LOCATIONS]
            location_query = " ".join(location_terms) if location_terms else entity_query
            queries = [
                f"{location_query} ready reckoner rate",
                f"{location_query} government valuation property rate",
                f"{location_query} IGR Maharashtra ready reckoner",
            ]
            return self._dedupe_queries(queries)

        if intent == "latest":
            queries.append(f"{entity_query} {expanded_terms} latest")
            queries.append(f"{entity_query} {expanded_terms} news")
        elif intent == "comparison":
            queries.append(f"{entity_query} {expanded_terms} comparison")
            queries.append(f"{entity_query} {expanded_terms} pros cons")
        elif intent == "pricing":
            queries.append(f"{entity_query} {expanded_terms} price cost")
            queries.append(f"{entity_query} {expanded_terms} rates")
        elif intent == "recommendation":
            queries.append(f"{entity_query} {expanded_terms} best top")
            queries.append(f"{entity_query} {expanded_terms} review")
        elif intent == "explanation":
            queries.append(f"{entity_query} {expanded_terms} meaning")
            queries.append(f"{entity_query} {expanded_terms} definition")
            queries.append(f"{entity_query} {expanded_terms} explained")
        elif expanded_terms:
            queries.append(f"{expanded_terms} meaning building regulations")
            queries.append(f"sanctioned {expanded_terms} development control rules")
        else:
            queries.append(f"{entity_query} overview")
            queries.append(f"{entity_query} official source")

        return self._dedupe_queries(queries)

    def _build_positive_terms(self, query: str, entities: List[str], domain_context: Dict) -> List[str]:
        terms = []
        terms.extend(entities)
        terms.extend(domain_context.get("expansions", []))
        terms.extend(domain_context.get("context_terms", [])[:5])
        terms.extend(self._important_terms(query))
        return self._dedupe_terms(terms)

    def _dedupe_queries(self, queries: List[str]) -> List[str]:
        deduped = []
        for item in queries:
            item = self._normalize_query(item)
            if item and item.lower() not in [q.lower() for q in deduped]:
                deduped.append(item)
        return deduped

    def _rank_result(
        self,
        result: SearchResult,
        understanding: QueryUnderstanding,
        search_query: str,
    ) -> Dict:
        haystack = f"{result.title} {result.snippet} {result.url}".lower()
        entities = [entity.lower() for entity in understanding.key_entities]
        matched_entities = [entity for entity in entities if self._contains_term(haystack, entity)]
        entity_score = len(matched_entities) / max(1, len(entities))
        topic_score = self._topic_overlap_score(haystack, understanding.positive_terms)
        query_score = self._topic_overlap_score(haystack, self._important_terms(understanding.original_query))
        phrase_score = self._phrase_score(haystack, understanding.original_query, search_query)

        domain = urlparse(result.url).netloc.lower()
        authority_score = self._authority_score(domain, understanding.intent, topic_score)
        penalty = self._irrelevant_result_penalty(haystack, understanding.key_entities, understanding.original_query)
        rank_score = max(0.0, 1.0 - ((result.rank or 1) - 1) * 0.08)

        relevance_score = round(
            max(
                0.0,
                (topic_score * 0.34)
                + (query_score * 0.24)
                + (entity_score * 0.18)
                + (phrase_score * 0.10)
                + (authority_score * 0.07)
                + (rank_score * 0.07)
                - penalty,
            ),
            4,
        )

        return {
            "url": result.url,
            "title": result.title,
            "snippet": result.snippet,
            "rank": result.rank,
            "source": result.source,
            "search_query": search_query,
            "matched_entities": matched_entities,
            "topic_score": round(topic_score, 4),
            "relevance_score": relevance_score,
        }

    def _authority_score(self, domain: str, intent: str, topic_score: float = 0.0) -> float:
        if not domain:
            return 0.0

        score = 0.25
        if domain.endswith(".gov") or ".gov." in domain:
            score += 0.30 if topic_score >= 0.25 else 0.05
        if domain.endswith(".edu") or ".edu." in domain:
            score += 0.20 if topic_score >= 0.25 else 0.05
        if any(marker in domain for marker in ["wikipedia.org", "docs.", "developer.", "support."]):
            score += 0.15
        if intent == "latest" and any(marker in domain for marker in ["news", "reuters", "apnews", "bbc", "ndtv"]):
            score += 0.15

        return min(score, 1.0)

    def _irrelevant_result_penalty(self, haystack: str, entities: List[str], query: str = "") -> float:
        penalty = 0.0
        entity_lowers = {entity.lower() for entity in entities}

        for acronym, details in DOMAIN_EXPANSIONS.items():
            if acronym not in entity_lowers:
                continue
            if any(term in haystack for term in details.get("avoid_terms", [])):
                penalty += 0.65
            if acronym == "fsi" and "ofsi" in haystack:
                penalty += 0.45
            if details["expanded"].lower() in haystack:
                penalty -= 0.25
            if any(term in haystack for term in details.get("context_terms", [])):
                penalty -= 0.15

        if self._is_property_rate_query(query.lower(), entity_lowers):
            if any(term in haystack for term in PROPERTY_RATE_AVOID_TERMS):
                penalty += 0.85
            if not any(term in haystack for term in PROPERTY_RATE_TERMS):
                penalty += 0.25
            if any(term in haystack for term in PROPERTY_RATE_TERMS):
                penalty -= 0.25

        for terms in GENERIC_OFF_TOPIC_TERMS.values():
            if any(term in haystack for term in terms) and not any(term in query.lower() for term in terms):
                penalty += 0.20

        return max(0.0, penalty)

    def _important_terms(self, text: str) -> List[str]:
        words = re.findall(r"[A-Za-z0-9][A-Za-z0-9.+#-]*", text.lower())
        return [
            word
            for word in words
            if word not in STOP_WORDS and len(word) >= 3
        ][:12]

    def _topic_overlap_score(self, text: str, terms: List[str]) -> float:
        if not terms:
            return 0.0

        weighted_total = 0.0
        matched_total = 0.0
        for term in terms:
            term = term.lower().strip()
            weight = 1.4 if " " in term else 1.0
            weighted_total += weight
            if self._contains_term(text, term):
                matched_total += weight

        return matched_total / max(weighted_total, 1.0)

    def _phrase_score(self, text: str, query: str, search_query: str) -> float:
        phrases = [
            self._normalize_query(query).lower(),
            self._normalize_query(search_query).lower(),
        ]
        for phrase in phrases:
            if len(phrase) >= 8 and phrase in text:
                return 1.0
        return 0.0

    def _dedupe_terms(self, terms: List[str]) -> List[str]:
        deduped = []
        for term in terms:
            term = self._normalize_query(str(term))
            if term and term.lower() not in [item.lower() for item in deduped]:
                deduped.append(term)
        return deduped

    def _contains_term(self, text: str, term: str) -> bool:
        term = term.lower().strip()
        if not term:
            return False
        if re.fullmatch(r"[a-z0-9]+", term):
            return re.search(rf"\b{re.escape(term)}\b", text) is not None
        return term in text
