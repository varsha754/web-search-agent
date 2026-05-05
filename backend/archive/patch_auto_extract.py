import sys

# 1. Patch main.py to set fetch_content=True by default in search()
with open('main.py', 'r', encoding='utf-8') as f:
    main_content = f.read()

target_main_1 = '''    def search(self, query: str, max_results: int = 5, 
               fetch_content: bool = False, use_cache: bool = True) -> Dict:'''
new_main_1 = '''    def search(self, query: str, max_results: int = 5, 
               fetch_content: bool = True, use_cache: bool = True) -> Dict:'''

if target_main_1 in main_content:
    main_content = main_content.replace(target_main_1, new_main_1)
    with open('main.py', 'w', encoding='utf-8') as f:
        f.write(main_content)
    print("Successfully patched main.py")
else:
    print("Could not find target_main_1 in main.py")


# 2. Patch analyzer.py to use content and add citations
with open('search_agent/analyzer.py', 'r', encoding='utf-8') as f:
    analyzer_content = f.read()

target_analyzer_1 = '''        # Prepare context for LLM
        context = []
        for i, result in enumerate(results[:5], 1):
            context.append(f"{i}. {result.get('title', '')[:120]}")
            context.append(f"   URL: {result.get('url', '')}")
            context.append(f"   Relevance score: {result.get('relevance_score', 'unknown')}")
            context.append(f"   Snippet: {result.get('snippet', '')[:260]}")
        
        context_str = "\\n".join(context)
        query_hint = self._get_query_hint(query)
        
        # Enhanced prompt for accurate answers to all query types
        prompt = f"""Based on the following search results for the query: "{query}"

Query Context:
{query_hint}

Search Results:
{context_str}

Extracted Information:
- Locations: {', '.join(keyword_insights['locations'][:3]) if keyword_insights['locations'] else 'None found'}
- Numbers/Data: {', '.join(keyword_insights['numbers'][:5]) if keyword_insights['numbers'] else 'None found'}
- Key Points: {', '.join(keyword_insights['key_points'][:3]) if keyword_insights['key_points'] else 'None found'}

Provide a clear, accurate, and concise answer to the user's query. Prefer sources with higher relevance scores. If a source is about a different topic or different meaning of an acronym, ignore it. If the search results are not relevant enough, say that clearly instead of guessing."""'''

new_analyzer_1 = '''        # Prepare context for LLM
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
        
        context_str = "\\n".join(context)
        query_hint = self._get_query_hint(query)
        
        # Enhanced prompt for accurate answers to all query types
        prompt = f"""Based on the following search results for the query: "{query}"

Query Context:
{query_hint}

Search Results:
{context_str}

Provide a clear, accurate, and comprehensive answer to the user's query. Extract EXACT data and information from the provided content. 
IMPORTANT INSTRUCTIONS:
1. Like ChatGPT, you MUST include citations in your text referencing the sources using their [number].
2. Provide a detailed, in-depth answer using the exact data from the content.
3. At the end of your answer, list a few URLs ("URLs to check in depth:") so the user can read more."""'''

if target_analyzer_1 in analyzer_content:
    analyzer_content = analyzer_content.replace(target_analyzer_1, new_analyzer_1)
    # Increase max_tokens for better answers
    analyzer_content = analyzer_content.replace('max_tokens=config.MAX_TOKENS,', 'max_tokens=config.MAX_TOKENS * 2,')
    with open('search_agent/analyzer.py', 'w', encoding='utf-8') as f:
        f.write(analyzer_content)
    print("Successfully patched analyzer.py")
else:
    print("Could not find target_analyzer_1 in analyzer.py")
