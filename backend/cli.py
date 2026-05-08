#!/usr/bin/env python3
"""
Enhanced CLI with LLM-powered web search
Uses OpenAI's web search tool for accurate results
"""

import argparse
import sys
import re
from datetime import datetime
from typing import Dict

# Add the current directory to path
sys.path.insert(0, '.')

from search_agent.searcher import DuckDuckGoSearcher, EnhancedSearcher
from agents.UI_dashboard.prompts import EnhancedAnalyzer
from search_agent.source_discovery import SourceDiscovery
from core.config import config


class DirectSearchAgent:
    """
    Direct search agent that searches EXACTLY what the user asks for
    No query modification or expansion - searches specifically for the given topic
    """
    
    # Common acronym disambiguation mappings
    AMBIGUOUS_TERMS = {
        'fsi': ['floor space index', 'udcpr fsi', 'building construction fsi'],
        'udcpr': ['maharashtra udcpr', 'udcpr 2020', 'maharashtra development control'],
        'dcpr': ['development control promotion regulations', 'maharashtra dcpr'],
        'rer': ['real estate regulation', 'rera act', 'real estate regulatory'],
        'oc': ['occupancy certificate', 'building oc'],
        'cc': ['completion certificate', 'building cc'],
    }
    
    def __init__(self):
        self.client = None
        self.total_tokens = 0
        self.total_cost = 0.0
        self.last_token_usage = None
        # Only try to initialize LLM if properly configured
        if config.USE_LLM and config.OPENAI_API_KEY and len(config.OPENAI_API_KEY) > 20:
            try:
                from openai import OpenAI
                self.client = OpenAI(api_key=config.OPENAI_API_KEY)
            except Exception as e:
                print(f"   âš ï¸ LLM not available: {e}")
    
    def get_token_report(self) -> dict:
        """Get token usage report"""
        return {
            'total_tokens': self.total_tokens,
            'total_cost': self.total_cost
        }
    
    def reset_token_count(self):
        """Reset token counter"""
        self.total_tokens = 0
        self.total_cost = 0.0
        self.last_token_usage = None
    
    def _disambiguate_query(self, query: str) -> str:
        """
        Disambiguate common acronyms to get more accurate results
        Replaces acronyms with full terms for better search results
        """
        import re
        
        # Check for FSI (standalone word) - replace with Floor Space Index
        # Use word boundary to match standalone FSI
        if re.search(r'\bfsi\b', query, re.IGNORECASE):
            # Check if it's already Floor Space Index
            if 'floor space index' not in query.lower():
                query = re.sub(r'\bfsi\b', 'Floor Space Index', query, flags=re.IGNORECASE)
        
        # Add maharashtra context for UDCPR/DCPR if not present
        if 'udcpr' in query.lower() and 'maharashtra' not in query.lower():
            query = query + " Maharashtra"
        
        if 'dcpr' in query.lower() and 'maharashtra' not in query.lower():
            query = query + " Maharashtra"
        
        return query
    
    def search_direct(self, query: str, max_results: int = 10, disambiguate: bool = True) -> dict:
        """
        Search DIRECTLY for the exact query provided - with optional disambiguation
        Uses LLM to provide accurate answers based on search results
        
        Args:
            query: The search query
            max_results: Maximum number of results to return
            disambiguate: Whether to disambiguate acronyms (default: True)
        """
        # Store original query
        original_query = query
        
        # Disambiguate query if enabled
        if disambiguate:
            disambiguated = self._disambiguate_query(query)
            if disambiguated != query:
                print(f"   â„¹ï¸  Disambiguated: '{query}' â†’ '{disambiguated}'")
                query = disambiguated
        
        print(f"\nðŸŽ¯ Direct Search: '{query}'")
        
        # Step 1: Discover real source URLs first.
        # The LLM is only used later to summarize these sources.
        searcher = DuckDuckGoSearcher()
        discovery = SourceDiscovery(searcher).discover(query, max_results=max_results)
        results = discovery["results"]
        
        if not results:
            return {
                'query': query,
                'success': False,
                'error': 'No results found',
                'results': [],
                'answer': None
            }
        
        # Step 2: Convert to dict format
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
            for r in results
        ]
        
        # Step 3: Use LLM to provide accurate answer
        answer = None
        self.last_token_usage = None
        if self.client:
            answer = self._get_llm_answer(query, results_dict)
        
        return {
            'query': query,
            'success': True,
            'results_count': len(results_dict),
            'results': results_dict,
            'answer': answer,
            'token_usage': self.last_token_usage,
            'discovery': discovery["understanding"],
            'search_type': 'direct'
        }
    
    def _get_llm_answer(self, query: str, results: list) -> str:
        """Use LLM to provide accurate answer from search results"""
        
        # Check for disambiguation needed
        query_lower = query.lower()
        context_hint = ""
        
        if 'fsi' in query_lower and 'forest' not in query_lower and 'survey' not in query_lower:
            context_hint = "NOTE: In this context, FSI means Floor Space Index (urban planning/real estate), NOT Forest Survey of India."
        
        # Prepare context from search results
        context = []
        for i, result in enumerate(results[:10], 1):
            title = result.get('title', '')[:150]
            snippet = result.get('snippet', '')[:300]
            context.append(f"{i}. {title}\n   {snippet}")
        
        context_str = "\n\n".join(context)
        
        prompt = f"""You are a helpful search assistant. Based on the following search results for the query: "{query}"

{context_hint}

Search Results:
{context_str}

Instructions:
1. Provide a clear, accurate, and comprehensive answer to the user's query
2. Use the information from the search results to answer directly
3. If the search results contain relevant data, synthesize it into a coherent answer
4. If the search results don't contain enough information, state that clearly
5. Be specific and focus on answering the exact question asked
6. If the query uses acronyms (like FSI, UDCPR, DCPR), interpret them in the context of the search results

Answer:"""

        try:
            response = self.client.chat.completions.create(
                model=config.LLM_MODEL,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=config.MAX_TOKENS * 2,  # Allow more tokens for comprehensive answers
                temperature=0.3
            )
            
            # Track token usage
            usage = response.usage
            input_tokens = usage.prompt_tokens if usage else 0
            output_tokens = usage.completion_tokens if usage else 0
            query_tokens = input_tokens + output_tokens
            
            # Calculate cost (GPT-4o-mini pricing: $0.15/1M input, $0.60/1M output)
            cost = (input_tokens / 1_000_000 * 0.15) + (output_tokens / 1_000_000 * 0.60)
            
            self.total_tokens += query_tokens
            self.total_cost += cost
            self.last_token_usage = {
                'input_tokens': input_tokens,
                'output_tokens': output_tokens,
                'total_tokens': query_tokens,
                'estimated_cost': round(cost, 6),
                'model': config.LLM_MODEL
            }
            
            print(f"   ðŸ”¢ Tokens used: {query_tokens} (input: {input_tokens}, output: {output_tokens})")
            print(f"   ðŸ’° Est. cost: ${cost:.6f}")
            
            return response.choices[0].message.content
            
        except Exception as e:
            print(f"   âš ï¸ LLM error: {e}")
            self.last_token_usage = None
            return None


class QueryOptimizer:
    """
    LLM-powered query optimizer that understands user intent
    and generates effective search queries for DuckDuckGo
    """
    
    def __init__(self):
        self.client = None
        self.total_tokens = 0
        self.total_cost = 0.0
        # Only try to initialize LLM if properly configured
        if config.USE_LLM and config.OPENAI_API_KEY and len(config.OPENAI_API_KEY) > 20:
            try:
                from openai import OpenAI
                self.client = OpenAI(api_key=config.OPENAI_API_KEY)
            except Exception as e:
                print(f"   âš ï¸ LLM not available: {e}")
    
    def get_token_report(self) -> dict:
        """Get token usage report"""
        return {
            'total_tokens': self.total_tokens,
            'total_cost': self.total_cost
        }
    
    def reset_token_count(self):
        """Reset token counter"""
        self.total_tokens = 0
        self.total_cost = 0.0
    
    def understand_intent(self, query: str) -> dict:
        """
        Use LLM to understand the query intent and extract key information
        """
        if not self.client:
            return self._simple_intent_detection(query)
        
        prompt = f"""Analyze this real estate search query and extract:
1. PRIMARY INTENT: (investment/buying/renting/comparison/research/news/pricing)
2. LOCATION: (specific area/city or null if not mentioned)
3. PROPERTY_TYPE: (2BHK/3BHK/flat/apartment/villa/plots/null)
4. KEY_TOPICS: (main subjects the user wants to know about)
5. TIME_CONTEXT: (current/past/future or null)

Query: "{query}"

Respond in JSON format:
{{
    "intent": "...",
    "location": "...",
    "property_type": "...",
    "key_topics": ["..."],
    "time_context": "..."
}}"""

        try:
            response = self.client.chat.completions.create(
                model=config.LLM_MODEL,
                messages=[
                    {"role": "system", "content": "You are a real estate search expert. Analyze queries to understand user intent."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=300,
                temperature=0.3
            )
            
            # Track token usage
            usage = response.usage
            input_tokens = usage.prompt_tokens if usage else 0
            output_tokens = usage.completion_tokens if usage else 0
            query_tokens = input_tokens + output_tokens
            
            # Calculate cost (GPT-4o-mini pricing: $0.15/1M input, $0.60/1M output)
            cost = (input_tokens / 1_000_000 * 0.15) + (output_tokens / 1_000_000 * 0.60)
            
            self.total_tokens += query_tokens
            self.total_cost += cost
            
            print(f"   ðŸ”¢ Tokens used: {query_tokens} (input: {input_tokens}, output: {output_tokens})")
            print(f"   ðŸ’° Est. cost: ${cost:.6f}")
            
            result_text = response.choices[0].message.content
            # Parse JSON from response
            import json
            # Extract JSON from response
            try:
                # Try to find JSON in the response
                start = result_text.find('{')
                end = result_text.rfind('}') + 1
                if start >= 0 and end > start:
                    return json.loads(result_text[start:end])
            except:
                pass
            
            return self._simple_intent_detection(query)
                
        except Exception as e:
            print(f"   âš ï¸ LLM error: {e}")
            return self._simple_intent_detection(query)
    
    def _simple_intent_detection(self, query: str) -> dict:
        """Fallback intent detection without LLM"""
        query_lower = query.lower()
        
        # Detect intent
        intent = "research"
        if any(w in query_lower for w in ['invest', 'investment', 'returns', 'appreciation']):
            intent = "investment"
        elif any(w in query_lower for w in ['buy', 'purchase', 'flat', 'apartment', 'house']):
            intent = "buying"
        elif any(w in query_lower for w in ['rent', 'rental', 'tenant', 'leasing']):
            intent = "renting"
        elif any(w in query_lower for w in ['price', 'cost', 'rate', 'budget', 'expensive', 'cheap']):
            intent = "pricing"
        elif any(w in query_lower for w in ['compare', 'vs', 'versus', 'better', 'best']):
            intent = "comparison"
        
        # Detect location
        pune_areas = ['wakad', 'baner', 'hinjewadi', 'kharadi', 'wagholi', 'nibm', 'punawale', 
                     'kondhwa', 'viman nagar', 'magarpatta', 'hadapsar', 'aundh', 'kothrud', 
                     'pimple saudagar', 'balewadi', 'mhalunge', 'pune']
        
        location = None
        for loc in pune_areas:
            if loc in query_lower:
                location = loc.title() if loc != 'pune' else 'Pune'
                break
        
        # Detect property type
        property_type = None
        if '2bhk' in query_lower or '2 bhk' in query_lower:
            property_type = "2BHK"
        elif '3bhk' in query_lower or '3 bhk' in query_lower:
            property_type = "3BHK"
        elif '4bhk' in query_lower or '4 bhk' in query_lower:
            property_type = "4BHK"
        
        return {
            "intent": intent,
            "location": location,
            "property_type": property_type,
            "key_topics": [],
            "time_context": "current"
        }
    
    def generate_search_queries(self, query: str, intent_info: dict) -> list:
        """
        Generate optimized search queries based on intent
        """
        queries = []
        year = datetime.now().year
        
        location = intent_info.get('location') or 'Pune'
        property_type = intent_info.get('property_type', '')
        intent = intent_info.get('intent', 'research')
        
        # Generate queries based on intent
        if intent == "investment":
            queries = [
                f"{location} real estate investment hotspots {year}",
                f"best areas to invest in {location} property returns",
                f"{location} property appreciation trends {year}"
            ]
        elif intent == "buying":
            queries = [
                f"buy property in {location} {property_type}",
                f"{location} real estate projects {year}",
                f"best residential areas in {location}"
            ]
        elif intent == "renting":
            queries = [
                f"rent in {location} property",
                f"{location} rental rates {year}",
                f"best areas for renting in {location}"
            ]
        elif intent == "pricing":
            queries = [
                f"{location} property prices {property_type} {year}",
                f"{location} real estate rates per sqft",
                f"{location} flat prices {year}"
            ]
        elif intent == "comparison":
            queries = [
                f"{location} areas comparison real estate",
                f"best vs worst areas in {location} property",
                f"{location} micro markets comparison"
            ]
        else:  # research
            queries = [
                f"{location} real estate market {year}",
                f"{location} property news trends",
                f"{location} real estate overview"
            ]
        
        # Add property type to queries if specified
        if property_type:
            queries = [q.replace('property', f'{property_type} property').replace('flat', f'{property_type} flat') for q in queries]
        
        return queries


class SmartSearchCLI:
    """CLI with intelligent query optimization using LLM"""
    
    def __init__(self):
        self.searcher = DuckDuckGoSearcher()
        self.optimizer = QueryOptimizer()
        self.total_queries = 0
    
    def get_stats(self) -> dict:
        """Get token usage statistics"""
        token_report = self.optimizer.get_token_report()
        return {
            'total_queries': self.total_queries,
            'total_tokens': token_report['total_tokens'],
            'total_cost': token_report['total_cost']
        }
    
    def reset_stats(self):
        """Reset statistics"""
        self.total_queries = 0
        self.optimizer.reset_token_count()
    
    def search(self, query: str, max_results: int = 5, search_type: str = "web") -> dict:
        """Search with LLM-powered intent understanding"""
        
        self.total_queries += 1
        print(f"\nðŸ” Analyzing: '{query}'")
        
        # Use LLM to understand intent and generate optimized queries
        intent_info = self.optimizer.understand_intent(query)
        print(f"   ðŸ“Š Intent: {intent_info.get('intent', 'unknown')}")
        print(f"   ðŸ“ Location: {intent_info.get('location', 'Pune')}")
        
        # Generate optimized search queries based on intent
        optimized_queries = self.optimizer.generate_search_queries(query, intent_info)
        
        results = None
        used_query = None
        
        # Try each optimized query until we get results
        for q in optimized_queries:
            print(f"\nðŸ”Ž Trying: '{q}'")
            results = self.searcher.search(q, max_results)
            if results:
                used_query = q
                break
        
        # If no results with optimized queries, try original
        if not results:
            print(f"\nðŸ” Trying original: '{query}'")
            results = self.searcher.search(query, max_results)
            if results:
                used_query = query
        
        if not results:
            return {
                'success': False,
                'original_query': query,
                'error': 'No results found'
            }
        
        return {
            'success': True,
            'original_query': query,
            'search_query': used_query,
            'intent': intent_info,
            'results_count': len(results),
            'results': results
        }
    
    def search_news(self, query: str, max_results: int = 5) -> dict:
        """Search news with LLM optimization"""
        print(f"\nðŸ“° Analyzing: '{query}'")
        
        intent_info = self.optimizer.understand_intent(query)
        optimized_queries = self.optimizer.generate_search_queries(query, intent_info)
        
        results = None
        used_query = None
        
        for q in optimized_queries:
            print(f"\nðŸ“° Trying: '{q}'")
            results = self.searcher.search_news(q, max_results)
            if results:
                used_query = q
                break
        
        if not results:
            results = self.searcher.search_news(query, max_results)
            if results:
                used_query = query
        
        if not results:
            return {
                'success': False,
                'original_query': query,
                'error': 'No news results found'
            }
        
        return {
            'success': True,
            'original_query': query,
            'results_count': len(results),
            'results': results
        }
    
    def format_results(self, result: dict):
        """Format and display results"""
        if not result['success']:
            print(f"\nâŒ {result.get('error', 'No results found')}")
            print("\n TIPS FOR BETTER RESULTS:")
            print("   â€¢ Use keywords instead of full sentences")
            print("   â€¢ Good: 'Pune investment hotspots 2026'")
            print("   â€¢ Good: 'best areas to invest in Pune'")
            print("   â€¢ Good: 'Wakad vs Baner investment comparison'")
            print("   â€¢ Bad: 'What do you consider better investment in pune?'")
            print("\nðŸ“ Try these working examples:")
            print("   python cli.py 'Pune best investment areas'")
            print("   python cli.py 'Wakad vs Baner real estate'")
            print("   python cli.py 'Hinjewadi property growth 2026'")
            return
        
        print(f"\n{'='*70}")
        print(f"ðŸ“Š SEARCH RESULTS")
        print(f"{'='*70}")
        print(f"ðŸ“Œ Your query: {result['original_query']}")
        if result.get('optimized'):
            print(f"âœ¨ Used: {result['search_query']}")
        print(f"ðŸ“ˆ Found: {result['results_count']} results")
        
        # Show token usage if available
        token_report = self.optimizer.get_token_report()
        if token_report['total_tokens'] > 0:
            print(f"ðŸ”¢ Total tokens used: {token_report['total_tokens']}")
            print(f"ðŸ’° Total cost: ${token_report['total_cost']:.6f}")
        
        print(f"{'='*70}\n")
        
        for i, res in enumerate(result['results'][:config.MAX_RESULTS_IN_RESPONSE], 1):
            title = res.title
            snippet = res.snippet
            url = res.url
            
            # Clean up snippet
            if len(snippet) > 250:
                snippet = snippet[:250] + "..."
            
            print(f"{i}. ðŸ“Œ {title}")
            print(f"   ðŸ“ {snippet}")
            print(f"   ðŸ”— {url}")
            print()
        
        print(f"{'='*70}\n")


class EnhancedSearchCLI:
    """CLI with quality indicators, trust scores, and confidence analysis."""

    def __init__(self):
        self.searcher = EnhancedSearcher()
        self.analyzer = EnhancedAnalyzer()

    def search(self, query: str, max_results: int = 5) -> Dict:
        print(f"\nðŸ” Enhanced search: '{query}'")
        print("-" * 50)

        results = self.searcher.search_with_quality(query, max_results)
        if not results:
            return {'success': False, 'error': 'No high-quality results found'}

        results_dict = [
            {
                'url': result.url,
                'title': result.title,
                'snippet': result.snippet,
                'rank': result.rank,
                'source': result.source,
                'quality_score': result.quality_score,
                'relevance_score': result.relevance_score,
                'content_type': result.content_type,
                'domain_authority': result.domain_authority,
                'is_recent': result.is_recent,
                'has_date': result.has_date,
                'word_count': result.word_count,
            }
            for result in results
        ]

        analysis = self.analyzer.analyze_with_confidence(query, results_dict)

        return {
            'success': True,
            'query': query,
            'results_count': len(results_dict),
            'results': results_dict,
            'analysis': analysis,
            'timestamp': datetime.now().isoformat(),
        }

    def format_results(self, result: Dict):
        if not result['success']:
            print(f"\nâŒ {result.get('error', 'No results found')}")
            return

        analysis = result.get('analysis', {})

        print(f"\n{'='*70}")
        print("ðŸ“Š ENHANCED SEARCH RESULTS")
        print(f"{'='*70}")
        print(f"ðŸ“Œ Query: {result['query']}")
        print(f"ðŸ“ˆ Found: {result['results_count']} results")
        print(f"ðŸŽ¯ Confidence: {analysis.get('confidence_level', 'Unknown')} ({analysis.get('confidence', 0)}%)")
        print(f"ðŸ“š Sources: {analysis.get('sources_used', 0)} total, {analysis.get('high_trust_sources', 0)} high-trust")

        token_usage = analysis.get('token_usage') or {}
        if token_usage.get('total_tokens', 0) > 0:
            print(f"ðŸ”¢ Input tokens: {token_usage.get('input_tokens', 0)}")
            print(f"ðŸ”¢ Output tokens: {token_usage.get('output_tokens', 0)}")
            print(f"ðŸ”¢ Total tokens: {token_usage.get('total_tokens', 0)}")
            print(f"ðŸ’° Est. cost: ${token_usage.get('total_cost', 0):.6f}")

        print(f"{'='*70}\n")

        print(f"ðŸ’¡ ANSWER:\n{analysis.get('answer', 'No answer generated')}\n")

        print("ðŸ“Œ SOURCES")
        print("-" * 70)
        source_scores = analysis.get('source_scores', [])
        score_by_url = {source.get('url'): source for source in source_scores}

        for i, source in enumerate(result.get('results', [])[:5], 1):
            trust = score_by_url.get(source.get('url'), {})
            trust_score = trust.get('trust_score', 0)
            trust_level = trust.get('trust_level', 'Unknown')
            trust_symbol = "ðŸŸ¢" if trust_score >= 70 else "ðŸŸ¡" if trust_score >= 40 else "ðŸ”´"
            print(f"{i}. {trust_symbol} {source.get('title', '')[:80]}")
            print(f"   Trust: {trust_score}% ({trust_level})")
            print(f"   Relevance: {source.get('relevance_score', 0):.1f}% | Quality: {source.get('quality_score', 0):.1f}%")
            print(f"   Type: {source.get('content_type', 'html')} | Domain authority: {source.get('domain_authority', 0):.1f}")
            print(f"   ðŸ”— {source.get('url', '')}")
            print()

        consistency = analysis.get('consistency', {})
        if consistency.get('contradictions'):
            print(f"âš ï¸ NOTE: {', '.join(consistency['contradictions'])}")
            print()

        print(f"{'='*70}\n")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="DuckDuckGo Web Search CLI - Direct & Smart Search",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
EXAMPLES:
  # Direct search (searches exactly what you ask)
  python cli.py "fsi sanctioned rule as per udcpr"
  python cli.py "latest AI news"
  python cli.py "python tutorial"
  
  # Smart search (expands query for real estate)
  python cli.py --smart "best investment areas in Pune"
  python cli.py --smart "Wakad vs Baner real estate"
  
  # News search
  python cli.py --news "real estate news"
  python cli.py --news "property market update"
        """
    )
    
    parser.add_argument("query", nargs="*", help="Search query")
    parser.add_argument("-n", "--max-results", type=int, default=10, help="Max results (default: 10)")
    parser.add_argument("--news", action="store_true", help="Search news only")
    parser.add_argument("--smart", action="store_true", help="Use smart search (query expansion for real estate)")
    parser.add_argument("--enhanced", action="store_true", help="Use enhanced search with quality/trust/confidence scoring")
    parser.add_argument("-i", "--interactive", action="store_true", help="Interactive mode")
    parser.add_argument("--direct", action="store_true", help="Use direct search (default - searches exactly what you ask)")
    
    args = parser.parse_args()

    if args.enhanced:
        enhanced_cli = EnhancedSearchCLI()

        if args.interactive or not args.query:
            print("\nðŸ” ENHANCED SEARCH CLI")
            print("=" * 50)
            print("Results include relevance, quality, trust, and confidence scores.")
            print("Type 'exit' to quit.")
            print("=" * 50)

            while True:
                try:
                    user_input = input("\nðŸ” Search: ").strip()
                    if not user_input:
                        continue
                    if user_input.lower() in ['exit', 'quit', 'q']:
                        print("\nðŸ‘‹ Goodbye!")
                        break

                    result = enhanced_cli.search(user_input, args.max_results)
                    enhanced_cli.format_results(result)
                except KeyboardInterrupt:
                    print("\n\nðŸ‘‹ Goodbye!")
                    break
            return

        query = " ".join(args.query)
        result = enhanced_cli.search(query, args.max_results)
        enhanced_cli.format_results(result)
        return
    
    # Determine search mode
    use_direct = not args.smart  # Default to direct search
    
    if use_direct:
        cli = DirectSearchAgent()
    else:
        cli = SmartSearchCLI()
    
    # Show tips in interactive mode
    if args.interactive or not args.query:
        print("\n" + "=" * 70)
        print("ðŸ¦† DUCKDUCKGO WEB SEARCH CLI")
        print("=" * 70)
        print("ðŸ’¡ SEARCH MODES:")
        print("   --direct (default): Searches EXACTLY what you ask")
        print("   --smart: Expands query for real estate research")
        print("=" * 70)
        print("\nðŸ“ Direct Search Examples:")
        print("   â†’ python cli.py 'fsi sanctioned rule as per udcpr'")
        print("   â†’ python cli.py 'latest AI news 2026'")
        print("   â†’ python cli.py 'python programming tutorial'")
        print("\nðŸ“ Smart Search Examples:")
        print("   â†’ python cli.py --smart 'Pune best investment areas'")
        print("   â†’ python cli.py --smart 'Wakad vs Baner property'")
        print("=" * 70)
    
    # Interactive mode
    if args.interactive or not args.query:
        print("\nCommands: /news <query>, /direct <query>, /smart <query>, /exit\n")
        while True:
            try:
                user_input = input("ðŸ” Search: ").strip()
                
                if not user_input:
                    continue
                
                if user_input.lower() in ['/exit', 'exit', 'quit']:
                    print("\nðŸ‘‹ Goodbye!")
                    break
                
                if user_input.lower().startswith('/news'):
                    query = user_input[5:].strip()
                    if query:
                        searcher = DuckDuckGoSearcher()
                        results = searcher.search_news(query, args.max_results)
                        print(f"\nðŸ“° Found {len(results)} news results for: '{query}'")
                        for i, r in enumerate(results, 1):
                            print(f"{i}. {r.title}")
                            print(f"   {r.snippet[:200]}...")
                            print(f"   ðŸ”— {r.url}\n")
                    else:
                        print("âŒ Please provide a search query")
                elif user_input.lower().startswith('/direct'):
                    query = user_input[7:].strip()
                    if query:
                        cli = DirectSearchAgent()
                        result = cli.search_direct(query, args.max_results)
                        format_direct_results(result)
                    else:
                        print("âŒ Please provide a search query")
                elif user_input.lower().startswith('/smart'):
                    query = user_input[6:].strip()
                    if query:
                        cli = SmartSearchCLI()
                        result = cli.search(query, args.max_results)
                        cli.format_results(result)
                    else:
                        print("âŒ Please provide a search query")
                elif user_input.lower().startswith('/extract'):
                    # Syntax: /extract https://example.com what is the title?
                    parts = user_input[8:].strip().split(' ', 1)
                    if len(parts) == 2:
                        url, query = parts
                        print(f"\nâ³ Extracting from {url}...")
                        from agents.UI_dashboard.main import DuckDuckGoSearchAgent
                        agent = DuckDuckGoSearchAgent()
                        result = agent.extract_from_url(url, query)
                        
                        if result.get('success'):
                            print(f"\n{'='*70}")
                            print(f"ðŸ“„ EXTRACTED DATA FROM URL")
                            print(f"{'='*70}")
                            print(f"ðŸ”— URL: {result['url']}")
                            print(f"ðŸ“Œ Title: {result.get('title', 'Unknown')}")
                            print(f"â“ Query: {result['query']}")
                            print(f"{'-'*70}")
                            print(f"ðŸ“‹ ANSWER:\n{result.get('extracted_data', '')}")
                            
                            if result.get('token_usage'):
                                usage = result['token_usage']
                                print(f"{'-'*70}")
                                print(f"ðŸ”¢ Total tokens: {usage['total_tokens']}")
                                print(f"ðŸ’° Est. cost: ${usage.get('total_cost', 0):.6f}")
                            print(f"{'='*70}\n")
                        else:
                            print(f"\nâŒ Error: {result.get('error', 'Unknown error')}")
                    else:
                        print("âŒ Please provide both URL and query. Example: /extract https://example.com what is this?")
                else:
                    # Use default mode (direct)
                    cli = DirectSearchAgent()
                    result = cli.search_direct(user_input, args.max_results)
                    format_direct_results(result)
                    
            except KeyboardInterrupt:
                print("\n\nðŸ‘‹ Goodbye!")
                break
        return
    
    # Single query mode
    query = " ".join(args.query)
    
    if args.news:
        searcher = DuckDuckGoSearcher()
        results = searcher.search_news(query, args.max_results)
        print(f"\nðŸ“° Found {len(results)} news results for: '{query}'")
        for i, r in enumerate(results, 1):
            print(f"{i}. {r.title}")
            print(f"   {r.snippet[:200]}...")
            print(f"   ðŸ”— {r.url}\n")
    else:
        # Default to direct search
        result = cli.search_direct(query, args.max_results)
        format_direct_results(result)


def format_direct_results(result: dict):
    """Format and display direct search results"""
    if not result['success']:
        print(f"\nâŒ {result.get('error', 'No results found')}")
        return
    
    print(f"\n{'='*70}")
    print(f"ðŸŽ¯ DIRECT SEARCH RESULTS")
    print(f"{'='*70}")
    print(f"ðŸ“Œ Query: {result['query']}")
    print(f"ðŸ“ˆ Found: {result['results_count']} results")
    
    # Show token usage if available
    if result.get('answer'):
        print(f"âœ… LLM Answer provided")

    if result.get('token_usage'):
        usage = result['token_usage']
        print(f"ðŸ”¢ Input tokens: {usage['input_tokens']}")
        print(f"ðŸ”¢ Output tokens: {usage['output_tokens']}")
        print(f"ðŸ”¢ Total tokens: {usage['total_tokens']}")
        print(f"ðŸ’° Est. cost: ${usage['estimated_cost']:.6f}")

    if result.get('discovery'):
        discovery = result['discovery']
        print(f"ðŸ§­ Intent: {discovery.get('intent', 'research')}")
        print(f"ðŸ”‘ Key entities: {', '.join(discovery.get('key_entities', [])) or 'None'}")
    
    print(f"{'='*70}\n")
    
    # Show LLM answer if available
    if result.get('answer'):
        print("ðŸ“‹ ANSWER:")
        print("-" * 70)
        print(result['answer'])
        print("-" * 70)
        print()
    
    # Show search results
    print("ðŸ“„ SEARCH RESULTS:")
    print("-" * 70)
    for i, res in enumerate(result['results'], 1):
        title = res.get('title', 'No title')
        snippet = res.get('snippet', 'No description')
        url = res.get('url', '')
        
        # Clean up snippet
        if len(snippet) > 200:
            snippet = snippet[:200] + "..."
        
        print(f"{i}. ðŸ“Œ {title}")
        print(f"   ðŸ“ {snippet}")
        if res.get('relevance_score') is not None:
            print(f"   â­ Relevance: {res.get('relevance_score')}")
        if url:
            print(f"   ðŸ”— {url}")
        else:
            print("   ðŸ”— No source URL returned")
        print()
    
    print(f"{'='*70}\n")


if __name__ == "__main__":
    main()
