import os

# 1. Patch analyzer.py
with open("search_agent/analyzer.py", "r", encoding="utf-8") as f:
    analyzer_content = f.read()

analyzer_content = analyzer_content.replace(
    "def analyze_results(self, query: str, results: List[Dict], keyword_insights: Dict = None) -> str:",
    "def analyze_results(self, query: str, results: List[Dict], keyword_insights: Dict = None, stream_callback=None) -> str:"
)

target_completion = """        try:
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
            
            return response.choices[0].message.content"""

replacement_completion = """        try:
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
                
                return response.choices[0].message.content"""

if target_completion in analyzer_content:
    analyzer_content = analyzer_content.replace(target_completion, replacement_completion)
    with open("search_agent/analyzer.py", "w", encoding="utf-8") as f:
        f.write(analyzer_content)
    print("Patched analyzer.py")
else:
    print("Failed to patch analyzer.py")

# 2. Patch main.py
with open("main.py", "r", encoding="utf-8") as f:
    main_content = f.read()

main_content = main_content.replace(
    "def search(self, query: str, max_results: int = config.MAX_RESULTS, fetch_content: bool = True, use_cache: bool = True) -> Dict:",
    "def search(self, query: str, max_results: int = config.MAX_RESULTS, fetch_content: bool = True, use_cache: bool = True, status_callback=None, stream_callback=None) -> Dict:"
)

main_content = main_content.replace(
    "discovery = self.discovery.discover(query, max_results)",
    "if status_callback: status_callback('Understanding query and discovering sources...')\\n        discovery = self.discovery.discover(query, max_results)"
)

main_content = main_content.replace(
    "content_results = self.processor.process_batch(urls)",
    "if status_callback: status_callback(f'Reading full content from {len(urls)} top sources...')\\n            content_results = self.processor.process_batch(urls)"
)

main_content = main_content.replace(
    "analysis = self.analyzer.analyze_results(query, results_dict, keyword_insights)",
    "if status_callback: status_callback('Analyzing data and generating answer...')\\n            analysis = self.analyzer.analyze_results(query, results_dict, keyword_insights, stream_callback=stream_callback)"
)

with open("main.py", "w", encoding="utf-8") as f:
    f.write(main_content)
print("Patched main.py")

