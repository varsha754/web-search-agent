import sys
import datetime

with open('main.py', 'r', encoding='utf-8') as f:
    content = f.read()

target = '    def format_response(self, result: Dict, format_type: str = "markdown") -> str:\n'

new_method = """    def extract_from_url(self, url: str, query: str) -> Dict:
        \"\"\"
        Extract exact data from a given URL based on a specific query, 
        similar to ChatGPT's behavior.
        \"\"\"
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
            
            prompt = f\"\"\"You are a helpful assistant that extracts exact information from a given webpage, just like ChatGPT.
Based on the following content from '{title}' (URL: {url}), answer the user's query exactly and concisely. Provide ONLY the extracted data asked for in the query.

Query: {query}

Content:
{context_text}

Extracted Data/Answer:\"\"\"
            
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

"""

if target in content:
    content = content.replace(target, new_method + target)
    with open('main.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Successfully patched main.py")
else:
    print("Could not find target in main.py")
