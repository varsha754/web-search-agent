import os
import re

with open("api.py", "r", encoding="utf-8") as f:
    api_content = f.read()

# 1. Add imports for streaming
if "from fastapi.responses import StreamingResponse" not in api_content:
    api_content = api_content.replace(
        "from fastapi import FastAPI, HTTPException, Query",
        "from fastapi import FastAPI, HTTPException, Query\nfrom fastapi.responses import StreamingResponse\nimport asyncio\nimport json\nimport threading"
    )

# 2. Add /api/chat_stream endpoint
chat_stream_code = """
@app.get("/api/chat_stream")
async def chat_stream(query: str = Query(..., min_length=1), no_cache: bool = False):
    async def event_generator():
        queue = asyncio.Queue()
        loop = asyncio.get_running_loop()
        
        def status_callback(msg):
            loop.call_soon_threadsafe(queue.put_nowait, {'type': 'status', 'content': msg})
            
        def stream_callback(msg):
            loop.call_soon_threadsafe(queue.put_nowait, {'type': 'chunk', 'content': msg})
            
        def run_search():
            try:
                result = agent.search(
                    query, 
                    max_results=config.MAX_RESULTS_IN_RESPONSE, 
                    use_cache=not no_cache,
                    status_callback=status_callback,
                    stream_callback=stream_callback
                )
                loop.call_soon_threadsafe(queue.put_nowait, {'type': 'done', 'result': result})
            except Exception as e:
                loop.call_soon_threadsafe(queue.put_nowait, {'type': 'error', 'content': str(e)})

        thread = threading.Thread(target=run_search)
        thread.start()
        
        while True:
            item = await queue.get()
            yield f"data: {json.dumps(item)}\\n\\n"
            if item['type'] in ['done', 'error']:
                break
                
    return StreamingResponse(event_generator(), media_type="text/event-stream")
"""

if "@app.get(\"/api/chat_stream\")" not in api_content:
    api_content = api_content + "\n" + chat_stream_code

# 3. Update HTML/JS to ChatGPT style
html_start = api_content.find('    <html>')
html_end = api_content.find('    """', html_start)

chat_html = """    <html>
    <head>
        <title>DuckDuckGo Search Agent</title>
        <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
        <style>
            body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; margin: 0; padding: 0; background: #343541; color: #d1d5db; display: flex; flex-direction: column; height: 100vh; }
            .header { background: #343541; padding: 15px 20px; text-align: center; border-bottom: 1px solid #4d4d4f; font-weight: 600; color: #ececf1; }
            .chat-container { flex: 1; overflow-y: auto; padding: 20px 0; }
            .message { padding: 25px 20px; display: flex; justify-content: center; }
            .message.user { background: #343541; }
            .message.assistant { background: #444654; }
            .message-content { max-width: 800px; width: 100%; font-size: 16px; line-height: 1.6; }
            .input-container { padding: 30px 20px; background: #343541; border-top: 1px solid #4d4d4f; display: flex; justify-content: center; }
            form { max-width: 800px; width: 100%; display: flex; position: relative; }
            input { flex: 1; padding: 15px 50px 15px 20px; border-radius: 12px; border: 1px solid #4d4d4f; background: #40414f; color: white; font-size: 16px; box-shadow: 0 0 15px rgba(0,0,0,0.1); outline: none; }
            input::placeholder { color: #8e8ea0; }
            button { position: absolute; right: 10px; top: 10px; bottom: 10px; background: #19c37d; color: white; border: none; border-radius: 8px; padding: 0 15px; cursor: pointer; font-weight: bold; }
            button:hover { background: #1a8859; }
            .status-update { color: #8e8ea0; font-size: 14px; font-style: italic; margin-bottom: 10px; display: flex; align-items: center; }
            .status-update::before { content: "ðŸ”„"; display: inline-block; margin-right: 8px; animation: spin 2s linear infinite; }
            @keyframes spin { 100% { transform: rotate(360deg); } }
            
            /* Markdown Styling */
            .markdown-content h1, .markdown-content h2, .markdown-content h3 { color: #ececf1; margin-top: 20px; margin-bottom: 10px; }
            .markdown-content p { margin-bottom: 15px; }
            .markdown-content a { color: #10a37f; }
            .markdown-content ul, .markdown-content ol { padding-left: 20px; margin-bottom: 15px; }
            .markdown-content strong { color: #fff; }
            
            /* Sources Styling */
            .sources-box { margin-top: 30px; background: #343541; border: 1px solid #4d4d4f; border-radius: 8px; padding: 15px; }
            .source-item { margin-bottom: 10px; }
            .source-item a { color: #19c37d; text-decoration: none; font-weight: 500; }
            .source-item a:hover { text-decoration: underline; }
            .source-item .url { font-size: 12px; color: #8e8ea0; }
            .blinking-cursor { display: inline-block; width: 8px; height: 16px; background: #ececf1; animation: blink 1s step-end infinite; vertical-align: middle; margin-left: 4px; }
            @keyframes blink { 50% { opacity: 0; } }
        </style>
    </head>
    <body>
        <div class="header">ðŸ¦† Search & Extract Agent</div>
        
        <div class="chat-container" id="chatContainer">
            <div class="message assistant">
                <div class="message-content">
                    <p>Hello! I am an AI agent with access to live web search. Ask me anything, and I'll search the web, read the best articles, and give you a beautifully formatted answer.</p>
                </div>
            </div>
        </div>
        
        <div class="input-container">
            <form id="searchForm">
                <input type="text" id="query" placeholder="Send a message..." required autocomplete="off">
                <button type="submit">Send</button>
            </form>
        </div>
        
        <script>
            const chatContainer = document.getElementById('chatContainer');
            const searchForm = document.getElementById('searchForm');
            const queryInput = document.getElementById('query');
            
            function appendMessage(role, contentHtml, id = null) {
                const msgDiv = document.createElement('div');
                msgDiv.className = `message ${role}`;
                if (id) msgDiv.id = id;
                msgDiv.innerHTML = `<div class="message-content">${contentHtml}</div>`;
                chatContainer.appendChild(msgDiv);
                chatContainer.scrollTop = chatContainer.scrollHeight;
                return msgDiv;
            }

            searchForm.onsubmit = async (e) => {
                e.preventDefault();
                const query = queryInput.value.trim();
                if (!query) return;
                
                // Add user message
                appendMessage('user', `<p>${query}</p>`);
                queryInput.value = '';
                
                // Create assistant message placeholder
                const msgId = 'msg-' + Date.now();
                const assistantMsg = appendMessage('assistant', 
                    `<div id="${msgId}-status" class="status-update">Starting agent...</div>
                     <div id="${msgId}-content" class="markdown-content"></div>
                     <span id="${msgId}-cursor" class="blinking-cursor"></span>
                     <div id="${msgId}-sources"></div>`, 
                    msgId
                );
                
                const statusDiv = document.getElementById(`${msgId}-status`);
                const contentDiv = document.getElementById(`${msgId}-content`);
                const cursorSpan = document.getElementById(`${msgId}-cursor`);
                const sourcesDiv = document.getElementById(`${msgId}-sources`);
                
                let fullText = '';
                
                try {
                    const response = await fetch(`/api/chat_stream?query=${encodeURIComponent(query)}`);
                    const reader = response.body.getReader();
                    const decoder = new TextDecoder('utf-8');
                    
                    while (true) {
                        const { done, value } = await reader.read();
                        if (done) break;
                        
                        const chunk = decoder.decode(value, { stream: true });
                        const lines = chunk.split('\\n');
                        
                        for (const line of lines) {
                            if (line.startsWith('data: ')) {
                                try {
                                    const data = JSON.parse(line.slice(6));
                                    
                                    if (data.type === 'status') {
                                        statusDiv.innerHTML = data.content;
                                    } else if (data.type === 'chunk') {
                                        if (statusDiv.style.display !== 'none') {
                                            statusDiv.style.display = 'none'; // Hide status once text starts streaming
                                        }
                                        fullText += data.content;
                                        contentDiv.innerHTML = marked.parse(fullText);
                                        chatContainer.scrollTop = chatContainer.scrollHeight;
                                    } else if (data.type === 'done') {
                                        cursorSpan.style.display = 'none';
                                        statusDiv.style.display = 'none';
                                        
                                        // Sometimes result is cached, so it has data.result.answer
                                        if (data.result.answer && !fullText) {
                                            contentDiv.innerHTML = marked.parse(data.result.answer);
                                        }
                                        
                                        if (data.result.results && data.result.results.length > 0) {
                                            let sourcesHtml = '<div class="sources-box"><h4>ðŸ“„ Sources Read</h4>';
                                            for (const r of data.result.results.slice(0, 3)) {
                                                sourcesHtml += `
                                                    <div class="source-item">
                                                        <a href="${r.url}" target="_blank">${r.title}</a><br>
                                                        <span class="url">${r.url}</span>
                                                    </div>
                                                `;
                                            }
                                            sourcesHtml += '</div>';
                                            sourcesDiv.innerHTML = sourcesHtml;
                                        }
                                        chatContainer.scrollTop = chatContainer.scrollHeight;
                                    } else if (data.type === 'error') {
                                        cursorSpan.style.display = 'none';
                                        statusDiv.innerHTML = 'âŒ Error: ' + data.content;
                                        statusDiv.style.color = '#ef4444';
                                        statusDiv.style.animation = 'none';
                                        statusDiv.className = '';
                                    }
                                } catch (e) {
                                    console.error('Error parsing SSE:', e, line);
                                }
                            }
                        }
                    }
                } catch (error) {
                    cursorSpan.style.display = 'none';
                    statusDiv.innerHTML = 'âŒ Network Error: ' + error.message;
                    statusDiv.style.color = '#ef4444';
                    statusDiv.className = '';
                }
            };
        </script>
    </body>
    </html>"""

api_content = api_content[:html_start] + chat_html + "\n" + api_content[html_end+7:]

with open("api.py", "w", encoding="utf-8") as f:
    f.write(api_content)
print("Patched api.py")
