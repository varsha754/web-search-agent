
            const chatContainer = document.getElementById('chatContainer');
            const searchForm = document.getElementById('searchForm');
            const queryInput = document.getElementById('query');
            
            const parseMarkdown = (text) => {
                if (typeof marked !== 'undefined') {
                    try {
                        return marked.parse ? marked.parse(text) : marked(text);
                    } catch (e) {
                        console.error('Markdown parse error:', e);
                    }
                }
                return `<pre style="white-space: pre-wrap; font-family: inherit;">${text}</pre>`;
            };
            
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
                    const response = await fetch(`/api/chat_stream?query=${encodeURIComponent(query)}&no_cache=true`);
                    const reader = response.body.getReader();
                    const decoder = new TextDecoder('utf-8');
                    
                    let buffer = '';
                    while (true) {
                        const { done, value } = await reader.read();
                        if (done) break;
                        
                        buffer += decoder.decode(value, { stream: true });
                        
                        let boundary = buffer.indexOf('\n\n');
                        while (boundary !== -1) {
                            const message = buffer.slice(0, boundary);
                            buffer = buffer.slice(boundary + 2);
                            
                            const lines = message.split('\n');
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
                                        contentDiv.innerHTML = parseMarkdown(fullText);
                                        chatContainer.scrollTop = chatContainer.scrollHeight;
                                    } else if (data.type === 'done') {
                                        cursorSpan.style.display = 'none';
                                        statusDiv.style.display = 'none';
                                        
                                        if (data.result.success === false) {
                                            contentDiv.innerHTML = '❌ Agent Error: ' + (data.result.error || 'No results found');
                                            contentDiv.style.color = '#ef4444';
                                            return;
                                        }
                                        
                                        // Sometimes result is cached, so it has data.result.analysis
                                        if (data.result.analysis && !fullText) {
                                            contentDiv.innerHTML = parseMarkdown(data.result.analysis);
                                        }
                                        
                                        if (data.result.results && data.result.results.length > 0) {
                                            let sourcesHtml = '<div class="sources-box"><h4>📄 Sources Read</h4>';
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
                                        statusDiv.innerHTML = '❌ Error: ' + data.content;
                                        statusDiv.style.color = '#ef4444';
                                        statusDiv.style.animation = 'none';
                                        statusDiv.className = '';
                                    }
                                } catch (e) {
                                    console.error('Error parsing SSE:', e, line);
                                }
                            }
                        }
                        boundary = buffer.indexOf('\n\n');
                    }
                } // This closes while (true)
            } catch (error) {
                alert("Critical UI Error: " + error.message);
                if (cursorSpan) cursorSpan.style.display = 'none';
                if (statusDiv) {
                    statusDiv.innerHTML = '❌ Network Error: ' + error.message;
                    statusDiv.style.color = '#ef4444';
                    statusDiv.className = '';
                }
            }
        };
        