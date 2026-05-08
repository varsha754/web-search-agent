import sys

with open('cli.py', 'r', encoding='utf-8') as f:
    content = f.read()

target = '''                elif user_input.lower().startswith('/smart'):
                    query = user_input[6:].strip()
                    if query:
                        cli = SmartSearchCLI()
                        result = cli.search(query, args.max_results)
                        cli.format_results(result)
                    else:
                        print("âŒ Please provide a search query")
                else:'''

new_code = '''                elif user_input.lower().startswith('/smart'):
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
                        print(f"\\nâ³ Extracting from {url}...")
                        from main import DuckDuckGoSearchAgent
                        agent = DuckDuckGoSearchAgent()
                        result = agent.extract_from_url(url, query)
                        
                        if result.get('success'):
                            print(f"\\n{'='*70}")
                            print(f"ðŸ“„ EXTRACTED DATA FROM URL")
                            print(f"{'='*70}")
                            print(f"ðŸ”— URL: {result['url']}")
                            print(f"ðŸ“Œ Title: {result.get('title', 'Unknown')}")
                            print(f"â“ Query: {result['query']}")
                            print(f"{'-'*70}")
                            print(f"ðŸ“‹ ANSWER:\\n{result.get('extracted_data', '')}")
                            
                            if result.get('token_usage'):
                                usage = result['token_usage']
                                print(f"{'-'*70}")
                                print(f"ðŸ”¢ Total tokens: {usage['total_tokens']}")
                                print(f"ðŸ’° Est. cost: ${usage.get('total_cost', 0):.6f}")
                            print(f"{'='*70}\\n")
                        else:
                            print(f"\\nâŒ Error: {result.get('error', 'Unknown error')}")
                    else:
                        print("âŒ Please provide both URL and query. Example: /extract https://example.com what is this?")
                else:'''

if target in content:
    content = content.replace(target, new_code)
    with open('cli.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Successfully patched cli.py")
else:
    print("Could not find target in cli.py")
