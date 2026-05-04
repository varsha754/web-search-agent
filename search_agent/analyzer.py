"""
LLM-based analysis - MINIMAL TOKEN USAGE
Only called when needed, uses GPT-4o-mini for cost efficiency
Token usage: 500-2000 per analysis
"""

import json
import re
from typing import List, Dict, Any, Optional
from datetime import datetime
from openai import OpenAI
import tiktoken
from config import config


class LightweightAnalyzer:
    """
    Lightweight analyzer using LLM for accurate answers to all query types
    Token usage: 500-2000 tokens per query
    """
    
    def __init__(self):
        self.client = None
        self.encoder = None
        
        if config.USE_LLM and config.OPENAI_API_KEY:
            self.client = OpenAI(api_key=config.OPENAI_API_KEY)
            self.encoder = tiktoken.encoding_for_model("gpt-4o-mini")
        
        self.token_usage = {
            'input_tokens': 0,
            'output_tokens': 0,
            'total_cost': 0.0,
            'query_count': 0
        }
    
    def needs_analysis(self, query: str, results: List) -> bool:
        """Determine if LLM analysis is needed"""
        # Always use LLM for accurate answers when available
        if self.client:
            return True
        
        # Use LLM only for complex queries
        complex_indicators = [
            'compare', 'analysis', 'trend', 'vs', 'versus',
            'highest', 'lowest', 'best', 'worst',
            'why', 'how', 'what is the difference'
        ]
        
        query_lower = query.lower()
        
        # Simple keyword extraction doesn't need LLM
        if len(results) <= 3 and not any(ind in query_lower for ind in complex_indicators):
            return False
        
        return True
    
    def extract_keyword_insights(self, results: List) -> Dict:
        """Extract insights without LLM (0 tokens)"""
        insights = {
            'key_points': [],
            'numbers': [],
            'dates': [],
            'locations': [],
            'entities': []
        }
        
        import re
        
        for result in results[:5]:
            text = f"{result.get('title', '')} {result.get('snippet', '')}"
            
            # Extract numbers with units
            number_patterns = [
                r'(\d+(?:,\d+)?)\s*(?:lakh|crore|units|sq\.?ft|%)',
                r'₹\s*(\d+(?:,\d+)?)\s*(?:lakh|crore)',
                r'(\d+)\s*(?:BHK|bhk|bedroom)'
            ]
            
            for pattern in number_patterns:
                matches = re.findall(pattern, text, re.IGNORECASE)
                insights['numbers'].extend(matches)
            
            # Extract locations (Indian cities)
            cities = ['Baner', 'Wakad', 'Hinjewadi', 'Kothrud', 'Pune', 'Mumbai', 'Bangalore']
            for city in cities:
                if city.lower() in text.lower():
                    insights['locations'].append(city)
            
            # Extract key sentences (simple)
            sentences = text.split('.')
            for sentence in sentences[:3]:
                if len(sentence) > 50 and len(sentence) < 200:
                    insights['key_points'].append(sentence.strip())
        
        # Deduplicate
        insights['key_points'] = list(set(insights['key_points']))[:5]
        insights['locations'] = list(set(insights['locations']))
        insights['numbers'] = list(set(insights['numbers']))[:10]
        
        return insights
    
    def analyze_results(self, query: str, results: List[Dict], keyword_insights: Dict = None, stream_callback=None) -> str:
        """Analyze search results using LLM for accurate answers to all query types"""
        
        if not self.client:
            return self._format_without_llm(query, results)
        
        if keyword_insights is None:
            keyword_insights = self.extract_keyword_insights(results)
        
        # Prepare context for LLM
        context = []
        for i, result in enumerate(results[:5], 1):
            context.append(f"[{i}] {result.get('title', '')[:120]}")
            context.append(f"   URL: {result.get('url', '')}")
            context.append(f"   Relevance score: {result.get('relevance_score', 'unknown')}")
            if result.get('content'):
                content = result.get('content')
                context.append(f"   Content: {content[:3000]}")
            else:
                context.append(f"   Snippet: {result.get('snippet', '')[:500]}")
        
        context_str = "\n".join(context)
        query_hint = self._get_query_hint(query)
        
        # Enhanced prompt for accurate answers to all query types
        prompt = f"""Based on the following search results for the query: "{query}"

Query Context:
{query_hint}

Search Results:
{context_str}

Provide a clear, accurate, and comprehensive answer to the user's query. Extract EXACT data and information from the provided content. 
IMPORTANT INSTRUCTIONS:
1. You MUST use rich Markdown formatting to make your answer visually beautiful and easy to read.
2. Use bolding (**text**), bullet points, and headers (### Header) where appropriate.
3. Strategically include relevant emojis (e.g. 🏢, 📊, 👉, 💡, etc.) for different sections or key points, exactly like ChatGPT does!
4. You MUST include inline citations in your text referencing the sources using their [number].
5. At the very end of your answer, list a few URLs under a "### 🔗 URLs to Check In Depth:" header so the user can read more."""
        
        try:
            if stream_callback:
                response = self.client.chat.completions.create(
                    model=config.LLM_MODEL,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=config.MAX_TOKENS * 2,
                    temperature=0.3,
                    stream=True
                )
                
                full_text = ""
                for chunk in response:
                    if chunk.choices and chunk.choices[0].delta.content:
                        content = chunk.choices[0].delta.content
                        full_text += content
                        stream_callback(content)
                        
                # Estimate tokens for streaming mode
                self.token_usage['input_tokens'] += len(prompt) // 4
                self.token_usage['output_tokens'] += len(full_text) // 4
                
                return full_text
            else:
                response = self.client.chat.completions.create(
                    model=config.LLM_MODEL,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=config.MAX_TOKENS * 2,
                    temperature=0.3
                )
                
                # Track token usage
                self.token_usage['input_tokens'] += response.usage.prompt_tokens
                self.token_usage['output_tokens'] += response.usage.completion_tokens
                
                # Calculate cost (GPT-4o-mini: $0.150/1M input, $0.600/1M output)
                input_cost = response.usage.prompt_tokens * 0.00000015
                output_cost = response.usage.completion_tokens * 0.0000006
                self.token_usage['total_cost'] += input_cost + output_cost
                
                return response.choices[0].message.content
            
        except Exception as e:
            print(f"LLM analysis failed: {e}")
            return self._format_without_llm(query, results)

    def _get_query_hint(self, query: str) -> str:
        query_lower = query.lower()
        if re.search(r"\bfsi\b", query_lower):
            return (
                "FSI means Floor Space Index in building, real estate, and town planning contexts. "
                "Do not interpret FSI as financial sanctions or OFSI unless the user explicitly asks about sanctions."
            )
        if re.search(r"\budcpr\b", query_lower):
            return "UDCPR means Unified Development Control and Promotion Regulations, usually Maharashtra building rules."
        return "Use the user's wording and source context to resolve any ambiguous acronyms."
    
    def _format_without_llm(self, query: str, results: List[Dict]) -> str:
        """Fallback formatting without LLM (0 tokens)"""
        response = f"Search results for: {query}\n\n"
        response += f"Found {len(results)} results.\n\n"
        
        for i, result in enumerate(results[:5], 1):
            response += f"{i}. **{result.get('title', 'No title')}**\n"
            response += f"   {result.get('snippet', 'No description')[:200]}\n"
            response += f"   🔗 {result.get('url', '')}\n\n"
        
        return response
    
    def get_token_report(self) -> Dict:
        """Get token usage report"""
        return {
            'input_tokens': self.token_usage['input_tokens'],
            'output_tokens': self.token_usage['output_tokens'],
            'total_cost': round(self.token_usage['total_cost'], 6),
            'cost_per_query': round(self.token_usage['total_cost'] / max(1, self.token_usage.get('query_count', 1)), 6)
        }


# Example usage
if __name__ == "__main__":
    analyzer = LightweightAnalyzer()
    
    sample_results = [
        {
            'title': '2BHK Flats in Baner - 100+ Properties Available',
            'snippet': 'Find 2BHK flats in Baner Pune. Prices range from ₹85 Lakhs to ₹1.2 Crores.',
            'url': 'https://example.com/baner-2bhk'
        }
    ]
    
    analysis = analyzer.analyze_results("2BHK supply in Baner", sample_results)
    print(analysis)
    print(f"\nToken usage: {analyzer.get_token_report()}")


class EnhancedAnalyzer:
    """
    Enhanced analyzer with confidence scoring and cross-source validation.

    This supports the architecture's Step 3: analysis and verification.
    It extracts facts, checks consistency, scores source trust, and then
    generates an answer with confidence indicators.
    """

    def __init__(self):
        self.client = None
        self.encoder = None
        self.token_usage = {
            'input_tokens': 0,
            'output_tokens': 0,
            'total_tokens': 0,
            'total_cost': 0.0
        }

        if config.USE_LLM and config.OPENAI_API_KEY:
            self.client = OpenAI(api_key=config.OPENAI_API_KEY)
            self.encoder = tiktoken.encoding_for_model("gpt-4o-mini")

    def extract_facts(self, results: List[Dict]) -> List[Dict]:
        """Extract facts from search results with source attribution."""
        facts = []

        for result in results[:10]:
            text = f"{result.get('title', '')} {result.get('snippet', '')}"
            numbers = re.findall(
                r'(?:₹|rs\.?)?\s*(\d+(?:,\d+)?(?:\.\d+)?)\s*(?:lakh|crore|units|sq\.?ft|sqft|%)',
                text,
                re.I,
            )
            dates = re.findall(r'\b(20\d{2})\b', text)
            locations = re.findall(
                r'\b(Wakad|Baner|Hinjewadi|Pune|Mumbai|Bangalore|Kharadi|Hadapsar|Aundh|Balewadi)\b',
                text,
                re.I,
            )

            if numbers or dates or locations:
                facts.append({
                    'source_url': result.get('url'),
                    'source_title': result.get('title'),
                    'numbers': numbers[:3],
                    'dates': dates[:2],
                    'locations': list(dict.fromkeys(locations))[:2],
                    'snippet': result.get('snippet', '')[:220],
                })

        return facts

    def validate_consistency(self, facts: List[Dict]) -> Dict:
        """Check basic consistency across multiple sources."""
        if len(facts) < 2:
            return {'is_consistent': True, 'confidence': 0.5, 'contradictions': [], 'source_count': len(facts)}

        all_numbers = []
        for fact in facts:
            all_numbers.extend(fact.get('numbers', []))

        contradictions = []
        if len(set(all_numbers)) > 1 and len(all_numbers) > 2:
            contradictions.append("Numerical data differs across sources")

        return {
            'is_consistent': len(contradictions) == 0,
            'confidence': 0.8 if not contradictions else 0.4,
            'contradictions': contradictions,
            'source_count': len(facts),
        }

    def generate_trust_score(self, result: Dict, query: str) -> Dict:
        """Generate a trust score for one source."""
        score = 50
        url = result.get('url', '').lower()
        title = result.get('title', '').lower()
        snippet = result.get('snippet', '').lower()
        current_year = datetime.now().year

        authoritative_domains = [
            '.gov.in', '.nic.in', 'wikipedia.org', 'timesofindia', 'economictimes',
            'moneycontrol', 'rera', 'maharera', 'igrmaharashtra'
        ]
        if any(domain in url for domain in authoritative_domains):
            score += 30

        if str(current_year) in snippet or str(current_year) in title:
            score += 15
        if re.search(r'\d+', snippet):
            score += 10
        if re.search(r'₹|rs\.?|rupees', snippet):
            score += 10
        if re.search(r'sq\.?ft|sqft|square feet', snippet):
            score += 10
        if result.get('quality_score'):
            score = max(score, int(result.get('quality_score', 0)))

        for indicator in ['sign up', 'login', 'newsletter', 'subscribe']:
            if indicator in snippet:
                score -= 10

        score = min(max(score, 0), 100)
        return {
            'score': score,
            'level': 'High' if score >= 70 else 'Medium' if score >= 40 else 'Low',
            'factors': {
                'authority': 'Good' if '.gov' in url or 'wikipedia' in url or 'rera' in url else 'Decent',
                'recency': 'Current' if str(current_year) in snippet or str(current_year) in title else 'Unknown',
                'data_richness': 'Good' if re.search(r'\d+', snippet) else 'Limited',
            },
        }

    def analyze_with_confidence(self, query: str, results: List[Dict]) -> Dict:
        """Analyze results with confidence scoring."""
        if not results:
            return {
                'answer': "No relevant results found.",
                'confidence': 0,
                'confidence_level': 'Low',
                'sources_used': 0,
                'high_trust_sources': 0,
                'source_scores': [],
                'consistency': {'is_consistent': False, 'confidence': 0, 'contradictions': ['No sources found']},
                'key_findings': [],
            }

        facts = self.extract_facts(results)
        consistency = self.validate_consistency(facts)

        source_scores = []
        for result in results[:5]:
            trust_score = self.generate_trust_score(result, query)
            source_scores.append({
                'url': result.get('url'),
                'title': result.get('title'),
                'trust_score': trust_score['score'],
                'trust_level': trust_score['level'],
                'factors': trust_score['factors'],
            })

        avg_trust = sum(s['trust_score'] for s in source_scores) / len(source_scores) if source_scores else 0
        overall_confidence = (avg_trust / 100) * consistency['confidence']

        if self.client:
            answer = self._generate_llm_answer(query, results, source_scores, consistency)
        else:
            answer = self._generate_basic_answer(query, results)

        return {
            'answer': answer,
            'confidence': round(overall_confidence * 100, 1),
            'confidence_level': 'High' if overall_confidence > 0.7 else 'Medium' if overall_confidence > 0.4 else 'Low',
            'sources_used': len(results),
            'high_trust_sources': len([s for s in source_scores if s['trust_score'] >= 70]),
            'source_scores': source_scores,
            'consistency': consistency,
            'key_findings': facts[:3],
            'token_usage': self.get_token_report(),
        }

    def _generate_llm_answer(
        self,
        query: str,
        results: List[Dict],
        source_scores: List[Dict],
        consistency: Dict,
    ) -> str:
        """Generate answer using LLM with confidence indicators."""
        context = []
        for i, result in enumerate(results[:5], 1):
            source_score = next((s for s in source_scores if s['url'] == result.get('url')), {})
            trust = source_score.get('trust_level', 'Unknown')
            context.append(
                f"[Source {i} - Trust: {trust}]\n"
                f"Title: {result.get('title', '')}\n"
                f"URL: {result.get('url', '')}\n"
                f"Snippet: {result.get('snippet', '')[:320]}\n"
            )

        prompt = f"""Answer this query based only on the provided sources.

Query: {query}

Sources:
{chr(10).join(context)}

Consistency Check: {'Consistent' if consistency['is_consistent'] else 'Some contradictions found'}
Contradictions: {', '.join(consistency.get('contradictions', [])) or 'None'}

Instructions:
1. Provide a concise, accurate answer.
2. If sources conflict, mention the discrepancy.
3. Include confidence level: High, Medium, or Low.
4. Cite source numbers that support the answer.
5. Do not use unrelated sources.

Answer:"""

        try:
            response = self.client.chat.completions.create(
                model=config.LLM_MODEL,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=config.MAX_TOKENS * 2,
                temperature=0.25,
            )

            input_tokens = response.usage.prompt_tokens
            output_tokens = response.usage.completion_tokens
            self.token_usage['input_tokens'] += input_tokens
            self.token_usage['output_tokens'] += output_tokens
            self.token_usage['total_tokens'] += input_tokens + output_tokens
            self.token_usage['total_cost'] += (input_tokens * 0.00000015) + (output_tokens * 0.0000006)

            return response.choices[0].message.content

        except Exception as e:
            print(f"LLM error: {e}")
            return self._generate_basic_answer(query, results)

    def _generate_basic_answer(self, query: str, results: List[Dict]) -> str:
        """Fallback answer generation without LLM."""
        answer = f"Based on {len(results)} sources for '{query}':\n\n"
        for i, result in enumerate(results[:3], 1):
            answer += f"{i}. {result.get('title', '')}\n"
            answer += f"   {result.get('snippet', '')[:180]}...\n"
            answer += f"   Source: {result.get('url', '')}\n\n"
        return answer

    def get_token_report(self) -> Dict:
        return {
            'input_tokens': self.token_usage['input_tokens'],
            'output_tokens': self.token_usage['output_tokens'],
            'total_tokens': self.token_usage['total_tokens'],
            'total_cost': round(self.token_usage['total_cost'], 6),
        }
