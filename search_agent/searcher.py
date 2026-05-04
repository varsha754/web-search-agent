"""
LLM-based Web Search Implementation using OpenAI Responses API
Uses GPT-4o's built-in web search tool for accurate results
"""

import time
from typing import List, Optional
from dataclasses import dataclass
from config import config
import hashlib
from datetime import datetime
from urllib.parse import urlparse


@dataclass
class SearchResult:
    """Individual search result with optional quality metrics."""
    url: str
    title: str
    snippet: str
    source: str = "openai-websearch"
    rank: int = 0
    content: str = ""
    relevance_score: float = 0.0
    quality_score: float = 0.0
    content_type: str = "html"
    fetch_time: float = 0.0
    word_count: int = 0
    has_date: bool = False
    domain_authority: float = 0.0
    is_recent: bool = False


class LLMBasedSearcher:
    """
    LLM-based search using OpenAI's web search tool
    Provides accurate, context-aware search results
    """
    
    def __init__(self):
        self.client = None
        self.request_delay = 1.0
        
        # Initialize OpenAI client if API key is available
        if config.USE_LLM and config.OPENAI_API_KEY:
            try:
                from openai import OpenAI
                self.client = OpenAI(api_key=config.OPENAI_API_KEY)
            except Exception as e:
                print(f"   âš ï¸ OpenAI client not available: {e}")
    
    def search(self, query: str, max_results: int = 10) -> List[SearchResult]:
        """
        Perform LLM-based web search using OpenAI's Responses API
        """
        print(f"🔍 Searching the web (LLM-powered): '{query}'")
        
        if not self.client:
            print("   ⚠️ OpenAI client not available")
            return []
        
        try:
            # Use OpenAI's Responses API with web_search_preview tool
            response = self.client.responses.create(
                model="gpt-4o",
                tools=[{"type": "web_search_preview"}],
                input=query,
                max_output_tokens=max_results * 500,
                temperature=0.3
            )
            
            search_results = []
            answer_text = ""
            
            # Process the response
            for item in response.output:
                if hasattr(item, 'type'):
                    if item.type == "web_search_call":
                        # Web search was performed
                        pass
                    elif item.type == "message":
                        # Get the text content
                        for content in item.content:
                            if content.type == "output_text":
                                answer_text = content.text
            
            # If we got an answer, create a synthetic result
            if answer_text:
                search_results.append(SearchResult(
                    url="",
                    title=f"LLM Web Search Results for: {query}",
                    snippet=answer_text[:500],
                    rank=1
                ))
                print(f"   ✓ Got LLM answer ({len(answer_text)} chars)")
            else:
                print(f"   ✗ No results found")
            
            return search_results
            
        except Exception as e:
            print(f"   ✗ LLM Search failed: {str(e)}")
            return []
    
    def search_with_context(self, query: str, context: str = "", max_results: int = 10) -> List[SearchResult]:
        """
        Search with additional context for better results
        """
        if context:
            query = f"{query}\n\nContext: {context}"
        
        return self.search(query, max_results)
    
    def search_news(self, query: str, max_results: int = 10) -> List[SearchResult]:
        """Search news using LLM"""
        # Add news context to query
        news_query = f"{query} latest news 2026"
        return self.search(news_query, max_results)


# Keep DuckDuckGo searcher for fallback
class DuckDuckGoSearcher:
    """
    DuckDuckGo search implementation using ddgs package
    (Fallback when LLM search is not available)
    """
    
    def __init__(self):
        try:
            from duckduckgo_search import DDGS
            self.ddgs = DDGS()
        except ImportError:
            print("   ⚠️ ddgs package not available")
            self.ddgs = None
        self.request_delay = 1.0
        
    def search(self, query: str, max_results: int = 5) -> List[SearchResult]:
        """
        Perform DuckDuckGo search
        """
        print(f"🔍 Searching DuckDuckGo: '{query}'")
        
        if not self.ddgs:
            print("   ✗ DuckDuckGo not available")
            return []
        
        try:
            # Using the new ddgs package
            results = list(self.ddgs.text(
                query,
                max_results=max_results,
                region='in-en'  # India region for better results
            ))
            
            search_results = []
            if results:
                for rank, result in enumerate(results, 1):
                    # Handle different response formats
                    url = result.get('href', result.get('url', ''))
                    title = result.get('title', '')
                    snippet = result.get('body', result.get('description', ''))
                    
                    if url and title:  # Only add if we have useful data
                        search_results.append(SearchResult(
                            url=url,
                            title=title,
                            snippet=snippet,
                            source="duckduckgo",
                            rank=rank
                        ))
            
            if search_results:
                print(f"   ✓ Found {len(search_results)} results")
            else:
                print(f"   ✗ No results found")
            
            return search_results
            
        except Exception as e:
            print(f"   ✗ DuckDuckGo search failed: {str(e)}")
            print(f"   ⚠️ Falling back to Bing Search...")
            return self._search_bing(query, max_results)
            
    def _search_bing(self, query: str, max_results: int = 5) -> List[SearchResult]:
        import requests
        from bs4 import BeautifulSoup
        import urllib.parse
        import base64
        import re
        
        search_results = []
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept-Language': 'en-US,en;q=0.9,en-IN;q=0.8'
            }
            url = f'https://www.bing.com/search?q={urllib.parse.quote(query)}&setmkt=en-IN&setlang=en'
            resp = requests.get(url, headers=headers, timeout=10)
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            for rank, li in enumerate(soup.find_all('li', class_='b_algo'), 1):
                title_tag = li.find('h2')
                if not title_tag: continue
                a_tag = title_tag.find('a')
                if not a_tag: continue
                link = a_tag.get('href', '')
                title = a_tag.text
                
                # Try to decode Bing redirect URL
                if 'bing.com/ck' in link:
                    match = re.search(r'u=a1([^&]+)', link)
                    if match:
                        try:
                            # Add padding if needed
                            b64_str = match.group(1)
                            b64_str += '=' * (-len(b64_str) % 4)
                            decoded = base64.b64decode(b64_str).decode('utf-8', errors='ignore')
                            if decoded.startswith('http'):
                                link = decoded
                        except:
                            pass
                
                snippet_tag = li.find('div', class_='b_caption') or li.find('p')
                snippet = snippet_tag.text if snippet_tag else ''
                
                # Filter out Chinese websites
                bad_domains = ['.cn/', '.cn', 'zh.wikipedia.org', 'baidu.com', 'weibo.com']
                if any(bad in link.lower() for bad in bad_domains):
                    continue
                
                if link and title:
                    search_results.append(SearchResult(
                        url=link,
                        title=title,
                        snippet=snippet,
                        source="bing",
                        rank=rank
                    ))
                    if len(search_results) >= max_results:
                        break
        except Exception as ex:
            print(f"   ✗ Bing fallback failed: {ex}")
        return search_results

    
    def search_news(self, query: str, max_results: int = 5) -> List[SearchResult]:
        """Search news specifically"""
        try:
            results = list(self.ddgs.news(
                query,
                max_results=max_results,
                region='in-en'
            ))
            
            search_results = []
            for rank, result in enumerate(results, 1):
                search_results.append(SearchResult(
                    url=result.get('url', ''),
                    title=result.get('title', ''),
                    snippet=result.get('body', ''),
                    source="duckduckgo-news",
                    rank=rank
                ))
            
            print(f"   ✓ Found {len(search_results)} news results")
            return search_results
            
        except Exception as e:
            print(f"   ✗ News search failed: {e}")
            return []
    
    def search_with_location(self, query: str, location: str, max_results: int = 5) -> List[SearchResult]:
        """Search with location context"""
        enhanced_query = f"{query} {location}"
        return self.search(enhanced_query, max_results)
    
    def get_search_hash(self, query: str) -> str:
        """Generate unique hash for caching"""
        return hashlib.md5(query.encode()).hexdigest()


class EnhancedSearcher:
    """
    Enhanced search with multi-query support and source quality scoring.

    This class keeps DuckDuckGo as the primary real-URL search provider, then adds
    source quality metrics so downstream analysis can prefer trustworthy sources.
    """

    DOMAIN_AUTHORITY = {
        "magicbricks.com": 85,
        "99acres.com": 88,
        "housing.com": 82,
        "squareyards.com": 75,
        "commonfloor.com": 70,
        "timesofindia.indiatimes.com": 90,
        "economictimes.indiatimes.com": 92,
        "moneycontrol.com": 85,
        "news18.com": 80,
        "wikipedia.org": 95,
        "gov.in": 98,
        "nic.in": 96,
        "maharashtra.gov.in": 95,
    }

    def __init__(self):
        self.base_searcher = DuckDuckGoSearcher()

    def search_with_quality(self, query: str, max_results: int = 10) -> List[SearchResult]:
        """Search and rank by combined relevance and quality score."""
        print(f"🔍 Enhanced Search: '{query}'")
        results = self._search_duckduckgo(query, max_results * 2)

        scored_results = []
        for result in results:
            result.content_type = self._detect_content_type(result.url)
            result.has_date = self._has_date(result)
            result.is_recent = self._is_recent(result)
            result.word_count = len(result.snippet.split())
            result.domain_authority = self._domain_authority(result.url)
            result.quality_score = self._calculate_quality_score(result)
            result.relevance_score = self._calculate_relevance_score(result, query)

            combined_score = (result.relevance_score * 0.7) + (result.quality_score * 0.3)
            scored_results.append((combined_score, result))

        scored_results.sort(key=lambda item: item[0], reverse=True)
        final_results = [result for score, result in scored_results[:max_results] if score >= 30]

        print(f"   ✓ Found {len(final_results)} high-quality results")
        return final_results

    def search_parallel(self, queries: List[str], max_results: int = 5) -> List[SearchResult]:
        """Search multiple query variants and deduplicate by URL."""
        all_results = []
        for query in queries:
            all_results.extend(self.search_with_quality(query, max_results))

        seen_urls = set()
        unique_results = []
        for result in all_results:
            if result.url in seen_urls:
                continue
            seen_urls.add(result.url)
            unique_results.append(result)

        unique_results.sort(
            key=lambda item: (item.relevance_score * 0.7) + (item.quality_score * 0.3),
            reverse=True,
        )
        return unique_results[:max_results]

    def _search_duckduckgo(self, query: str, max_results: int) -> List[SearchResult]:
        return self.base_searcher.search(query, max_results=max_results)

    def _calculate_quality_score(self, result: SearchResult) -> float:
        score = 50.0
        score = max(score, result.domain_authority)

        title = result.title.lower()
        snippet = result.snippet.lower()

        if len(result.title) > 30:
            score += 5
        if any(word in title for word in ["official", "government", "rera", "guideline", "notification"]):
            score += 10
        if result.is_recent:
            score += 8
        if len(result.snippet) > 100:
            score += 5
        if any(word in snippet for word in ["price", "rate", "unit", "sqft", "sq.ft", "bhk", "rule", "act"]):
            score += 10
        if result.content_type == "pdf":
            score += 5

        if any(word in snippet for word in ["login", "sign up", "subscribe", "newsletter"]):
            score -= 10

        return min(max(score, 0), 100)

    def _calculate_relevance_score(self, result: SearchResult, query: str) -> float:
        query_words = [
            word.lower()
            for word in query.split()
            if len(word) > 2 and word.lower() not in {"what", "how", "the", "and", "for", "with"}
        ]
        text = f"{result.title.lower()} {result.snippet.lower()} {result.url.lower()}"

        if not query_words:
            return 0.0

        matched_words = sum(1 for word in query_words if word in text)
        keyword_score = (matched_words / len(query_words)) * 100

        if query.lower() in text:
            keyword_score += 20

        return min(keyword_score, 100)

    def _domain_authority(self, url: str) -> float:
        domain = urlparse(url).netloc.lower().replace("www.", "")
        for known_domain, authority in self.DOMAIN_AUTHORITY.items():
            if known_domain in domain:
                return float(authority)
        if domain.endswith(".gov.in") or domain.endswith(".nic.in"):
            return 92.0
        if ".gov." in domain or domain.endswith(".gov"):
            return 85.0
        if domain.endswith(".edu") or ".edu." in domain:
            return 80.0
        return 50.0

    def _detect_content_type(self, url: str) -> str:
        path = urlparse(url).path.lower()
        if path.endswith(".pdf"):
            return "pdf"
        if path.endswith(".json"):
            return "json"
        return "html"

    def _has_date(self, result: SearchResult) -> bool:
        text = f"{result.title} {result.snippet}"
        return any(str(year) in text for year in range(datetime.now().year - 3, datetime.now().year + 1))

    def _is_recent(self, result: SearchResult) -> bool:
        current_year = datetime.now().year
        text = f"{result.title} {result.snippet}".lower()
        return str(current_year) in text or str(current_year - 1) in text or "latest" in text
