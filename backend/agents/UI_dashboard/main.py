"""
DuckDuckGo Web Search Agent - Main Entry Point
Complete working agent with minimal token usage
"""

import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime
import sys
from dataclasses import asdict

from tools.search import DuckDuckGoSearcher
from tools.discovery import SourceDiscovery
from tools.browser import ContentProcessor
from agents.UI_dashboard.prompts import LightweightAnalyzer
from agents.UI_dashboard.tools import ResponseFormatter
from database.db import SearchCache
from core.config import config
from utils.validation import AccuracyValidator

SEARCH_CACHE_VERSION = "source-discovery-v5"


class DuckDuckGoSearchAgent:
    """
    Complete search agent using free DuckDuckGo API
    Token usage: Only for LLM analysis (500-2000 tokens per complex query)
    """
    
    def __init__(self):
        # Primary searcher is DuckDuckGo (with Bing fallback)
        self.searcher = DuckDuckGoSearcher()
        self.discovery = SourceDiscovery(self.searcher)
        self.processor = ContentProcessor()
        self.analyzer = LightweightAnalyzer()
        self.formatter = ResponseFormatter()
        self.cache = SearchCache() if config.CACHE_ENABLED else None
        self.validator = AccuracyValidator()
        
        # Stats
        self.stats = {
            'queries': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'total_tokens': 0,
            'total_cost': 0.0
        }
    
    def search(self, query: str, max_results: int = 5, 
               fetch_content: bool = True, use_cache: bool = True, status_callback=None, stream_callback=None) -> Dict:
        """
        Perform search and return results
        
        Args:
            query: Search query
            max_results: Number of results to return
            fetch_content: Whether to fetch full page content
            use_cache: Whether to use cache
        
        Returns:
            Dictionary with search results and analysis
        """
        
        cache_query = f"{SEARCH_CACHE_VERSION}:{query}"

        # Check cache
        if use_cache and self.cache:
            cached = self.cache.get(cache_query)
            if cached:
                self.stats['cache_hits'] += 1
                cached['cached'] = True
                return cached
        
        self.stats['cache_misses'] += 1
        self.stats['queries'] += 1
        
        # Step 1: Query understanding and source discovery
        if status_callback: status_callback('Understanding query and discovering sources...')
        discovery = self.discovery.discover(query, max_results)
        search_results = discovery["results"]
        
        if not search_results:
            return {
                'query': query,
                'success': False,
                'error': 'No results found',
                'results': []
            }
        
        # Convert to dict format
        results_dict = [
            {
                'url': r['url'],
                'title': r['title'],
                'snippet': r['snippet'],
                'rank': r['rank'],
                'source': r.get('source'),
                'search_query': r.get('search_query'),
                'matched_entities': r.get('matched_entities', []),
                'relevance_score': r.get('relevance_score', 0.0)
            }
            for r in search_results
        ]
        
        # Fetch full content if requested
        if fetch_content:
            urls = [r['url'] for r in search_results[:3]]
            if status_callback: status_callback(f'Reading full content from {len(urls)} top sources...')
            content_results = self.processor.process_batch(urls)
            
            # Filter and Merge content
            intent = discovery.get("understanding", {}).get("intent")
            if content_results:
                final_results = []
                for result in results_dict:
                    found_content = False
                    for content in content_results:
                        if content and result['url'] == content.get('url'):
                            # Apply real estate filtering for construction queries
                            content_text = content.get('content', '')
                            if intent == "construction_status":
                                if self.processor._is_tourism_content(content_text):
                                    if status_callback: status_callback(f"Skipping tourism content: {result['url'][:30]}...")
                                    continue
                                if not self.processor._is_real_estate_content(content_text):
                                    # If not clearly real estate, but not tourism, we might keep it but lower trust
                                    pass

                            result['content'] = content_text
                            result['title'] = content.get('title') or result['title']
                            result['published_date'] = content.get('published_date')
                            result['time_ago'] = content.get('time_ago', 'Date unknown')
                            result['source_trust'] = content.get('source_trust', 0.5)
                            result['extracted_data'] = content.get('extracted_data')
                            found_content = True
                            break
                    if found_content or not fetch_content:
                        final_results.append(result)
                results_dict = final_results
        
        # Analyze if needed - always use LLM when available for accurate answers
        analysis = None
        token_before = self.analyzer.get_token_report()
        if self.analyzer.needs_analysis(query, results_dict):
            if status_callback: status_callback('Analyzing data and generating trusted answer...')
            intent = discovery.get("understanding", {}).get("intent")
            trusted_response = self.analyzer.generate_trusted_answer(
                query, results_dict, self.validator, intent=intent, stream_callback=stream_callback
            )
            analysis = trusted_response['answer']
            output_metadata = {
                'accuracy_score': trusted_response['accuracy_score'],
                'confidence_level': trusted_response['confidence_level'],
                'recommendation': trusted_response['recommendation'],
                'validated_claims': trusted_response['validated_claims']
            }
        else:
            output_metadata = {}
        
        # Prepare output
        output = {
            'query': query,
            'success': True,
            'discovery': discovery["understanding"],
            'discovery_token_usage': discovery.get("token_usage"),
            'results_count': len(results_dict),
            'results': results_dict,
            'analysis': analysis,
            'accuracy': output_metadata,
            'timestamp': datetime.now().isoformat()
        }
        
        # Add token usage
        token_after = self.analyzer.get_token_report()
        token_report = {
            'input_tokens': token_after['input_tokens'] - token_before['input_tokens'],
            'output_tokens': token_after['output_tokens'] - token_before['output_tokens'],
            'total_cost': round(token_after['total_cost'] - token_before['total_cost'], 6),
        }
        token_report['total_tokens'] = token_report['input_tokens'] + token_report['output_tokens']
        output['token_usage'] = token_report
        discovery_tokens = discovery.get("token_usage") or {}
        self.stats['total_tokens'] += token_report['total_tokens'] + discovery_tokens.get('total_tokens', 0)
        self.stats['total_cost'] += token_report['total_cost'] + discovery_tokens.get('total_cost', 0.0)
        
        # Cache results
        if use_cache and self.cache:
            self.cache.set(cache_query, output)
        
        # Convert any dataclasses to dicts for JSON serialization at the very end
        for result in results_dict:
            extracted = result.get('extracted_data')
            if extracted and hasattr(extracted, '__dataclass_fields__'):
                result['extracted_data'] = asdict(extracted)

        return output
    
    async def search_async(self, query: str, max_results: int = 5) -> Dict:
        """Async version of search"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.search, query, max_results)
    
    def search_news(self, query: str, max_results: int = 5) -> Dict:
        """Search news specifically"""
        results = self.searcher.search_news(query, max_results)
        
        results_dict = [
            {
                'url': r.url,
                'title': r.title,
                'snippet': r.snippet,
                'rank': i + 1
            }
            for i, r in enumerate(results)
        ]
        
        return {
            'query': query,
            'success': True,
            'type': 'news',
            'results_count': len(results_dict),
            'results': results_dict,
            'timestamp': datetime.now().isoformat()
        }
    
    def extract_from_url(self, url: str, query: str) -> Dict:
        """
        Extract exact data from a given URL based on a specific query, 
        similar to ChatGPT's behavior.
        """
        self.stats['queries'] += 1
        
        # Fetch the content
        content_results = self.processor.process_batch([url])
        
        if not content_results:
            return {
                'url': url,
                'query': query,
                'success': False,
                'error': 'Failed to fetch content from URL'
            }
            
        content_data = content_results[0]
        content_text = content_data.get('content', '')
        title = content_data.get('title', '')
        
        if not content_text:
            return {
                'url': url,
                'query': query,
                'success': False,
                'error': 'No readable content found at URL'
            }
            
        # Use LLM to extract exact answer
        token_before = self.analyzer.get_token_report()
        
        if self.analyzer.client:
            # We want to give the LLM enough context but not exceed token limits
            # gpt-4o-mini can handle large contexts, let's limit to ~30k chars
            context_text = content_text[:30000]
            
            prompt = f"""You are a helpful assistant that extracts exact information from a given webpage, just like ChatGPT.
Based on the following content from '{title}' (URL: {url}), answer the user's query exactly and concisely. Provide ONLY the extracted data asked for in the query.

Query: {query}

Content:
{context_text}

Extracted Data/Answer:"""
            
            try:
                response = self.analyzer.client.chat.completions.create(
                    model=config.LLM_MODEL,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=config.MAX_TOKENS,
                    temperature=0.2
                )
                
                # Track tokens
                input_tokens = response.usage.prompt_tokens
                output_tokens = response.usage.completion_tokens
                
                self.analyzer.token_usage['input_tokens'] += input_tokens
                self.analyzer.token_usage['output_tokens'] += output_tokens
                
                cost = (input_tokens * 0.00000015) + (output_tokens * 0.0000006)
                self.analyzer.token_usage['total_cost'] += cost
                
                answer = response.choices[0].message.content
                
            except Exception as e:
                answer = f"Failed to analyze with LLM: {str(e)}"
        else:
            answer = "LLM is not configured. Cannot extract exact data."
            
        token_after = self.analyzer.get_token_report()
        token_report = {
            'input_tokens': token_after['input_tokens'] - token_before['input_tokens'],
            'output_tokens': token_after['output_tokens'] - token_before['output_tokens'],
            'total_cost': round(token_after['total_cost'] - token_before['total_cost'], 6),
        }
        token_report['total_tokens'] = token_report['input_tokens'] + token_report['output_tokens']
        
        self.stats['total_tokens'] += token_report['total_tokens']
        self.stats['total_cost'] += token_report['total_cost']
        
        return {
            'url': url,
            'query': query,
            'success': True,
            'title': title,
            'extracted_data': answer,
            'token_usage': token_report,
            'timestamp': datetime.now().isoformat()
        }

    def format_response(self, result: Dict, format_type: str = "markdown") -> str:
        """Format the search result"""
        results = result.get('results', [])
        analysis = result.get('analysis')
        cached = result.get('cached', False)
        discovery = result.get('discovery')
        
        if format_type == "markdown":
            return self.formatter.format_markdown(
                result['query'], results, analysis, cached, discovery
            )
        elif format_type == "json":
            return self.formatter.format_json(
                result['query'], results, analysis, 
                result.get('token_usage'), cached, discovery
            )
        else:
            return self.formatter.format_text(result['query'], results, analysis, discovery)
    
    def get_stats(self) -> Dict:
        """Get agent statistics"""
        return {
            **self.stats,
            'cache_stats': self.cache.stats() if self.cache else {'enabled': False},
            'llm_enabled': config.USE_LLM,
            'llm_model': config.LLM_MODEL if config.USE_LLM else None
        }


# Command-line interface
def main():
    """Command-line interface"""
    agent = DuckDuckGoSearchAgent()
    
    print("=" * 60)
    print("🦆 DUCKDUCKGO WEB SEARCH AGENT")
    print("=" * 60)
    print(f"LLM Analysis: {'Enabled' if config.USE_LLM else 'Disabled'}")
    print(f"Cache: {'Enabled' if config.CACHE_ENABLED else 'Disabled'}")
    print(f"Max Results: {config.DDG_MAX_RESULTS}")
    print("=" * 60)
    print("Type 'exit' to quit, 'stats' for statistics\n")
    
    while True:
        try:
            query = input("🔍 Enter search query: ").strip()
            
            if query.lower() in ['exit', 'quit', 'q']:
                print("\nGoodbye! 👋")
                break
            
            if query.lower() == 'stats':
                stats = agent.get_stats()
                print(f"\n📊 STATISTICS")
                print(f"   Queries: {stats['queries']}")
                print(f"   Cache hits: {stats['cache_hits']}")
                print(f"   Cache misses: {stats['cache_misses']}")
                print(f"   Total tokens: {stats['total_tokens']}")
                print(f"   Total cost: ${stats['total_cost']:.6f}")
                if stats.get('cache_stats', {}).get('enabled'):
                    print(f"   Cache entries: {stats['cache_stats'].get('total_entries', 0)}")
                print()
                continue
            
            if not query:
                continue
            
            print("\n⏳ Searching...")
            result = agent.search(query, max_results=config.MAX_RESULTS_IN_RESPONSE)
            
            if result['success']:
                formatted = agent.format_response(result, format_type="markdown")
                print("\n" + formatted)
                print(f"\n📈 Found {result['results_count']} results")
                
                if result.get('token_usage'):
                    tu = result['token_usage']
                    print(f"💰 Tokens used: {tu['input_tokens'] + tu['output_tokens']} (${tu['total_cost']:.6f})")
            else:
                print(f"\n❌ Error: {result.get('error', 'Unknown error')}")
            
            print("\n" + "-" * 40 + "\n")
            
        except KeyboardInterrupt:
            print("\n\nGoodbye! 👋")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}\n")


if __name__ == "__main__":
    main()
