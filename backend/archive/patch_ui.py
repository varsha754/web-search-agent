import sys

with open('api.py', 'r', encoding='utf-8') as f:
    content = f.read()

target_html = '''        <h1>🦆 DuckDuckGo Search Agent</h1>
        <form id="searchForm">
            <input type="text" id="query" placeholder="Enter your search query..." required>
            <button type="submit">Search</button>
        </form>
        <div id="results"></div>'''

new_html = '''        <h1>🦆 DuckDuckGo Search Agent</h1>
        
        <div style="margin-bottom: 30px; padding: 20px; background: #f9f9f9; border-radius: 8px;">
            <h3>🔍 Web Search</h3>
            <form id="searchForm">
                <input type="text" id="query" placeholder="Enter your search query..." required style="width: 70%;">
                <button type="submit">Search</button>
            </form>
        </div>

        <div style="margin-bottom: 30px; padding: 20px; background: #f0f7ff; border-radius: 8px;">
            <h3>📄 Extract from URL</h3>
            <p style="font-size: 14px; color: #666;">Extract specific information from a given URL exactly as requested.</p>
            <form id="extractForm">
                <input type="url" id="extractUrl" placeholder="Enter URL (https://...)" required style="width: 30%;"><br>
                <input type="text" id="extractQuery" placeholder="What do you want to extract?" required style="width: 70%;">
                <button type="submit">Extract</button>
            </form>
        </div>
        
        <div id="results"></div>'''

target_script = '''        <script>
            document.getElementById('searchForm').onsubmit = async (e) => {'''

new_script = '''        <script>
            document.getElementById('extractForm').onsubmit = async (e) => {
                e.preventDefault();
                const url = document.getElementById('extractUrl').value;
                const query = document.getElementById('extractQuery').value;
                const resultsDiv = document.getElementById('results');
                resultsDiv.innerHTML = '<p>Extracting data...</p>';
                
                try {
                    const response = await fetch(`/api/extract?url=${encodeURIComponent(url)}&query=${encodeURIComponent(query)}`);
                    const data = await response.json();
                    
                    if (data.success) {
                        let html = `<div class="analysis">
                            <strong>📄 Extracted Data from: </strong> <a href="${data.url}" target="_blank">${data.title || data.url}</a><br><br>
                            <div style="white-space: pre-wrap; font-family: monospace; background: white; padding: 15px; border-radius: 5px; border: 1px solid #ddd;">${data.extracted_data}</div>
                        </div>`;
                        
                        if (data.token_usage) {
                            html += `
                                <div class="analysis">
                                    <strong>Token Usage</strong><br>
                                    Input tokens: ${data.token_usage.input_tokens || 0}<br>
                                    Output tokens: ${data.token_usage.output_tokens || 0}<br>
                                    Total tokens: ${data.token_usage.total_tokens || 0}<br>
                                    Estimated cost: $${Number(data.token_usage.total_cost || 0).toFixed(6)}
                                </div>
                            `;
                        }
                        resultsDiv.innerHTML = html;
                    } else {
                        resultsDiv.innerHTML = `<p style="color: red;">Error: ${data.detail || data.error || 'Failed to extract'}</p>`;
                    }
                } catch (error) {
                    resultsDiv.innerHTML = `<p style="color: red;">Error: ${error.message}</p>`;
                }
            };

            document.getElementById('searchForm').onsubmit = async (e) => {'''

if target_html in content and target_script in content:
    content = content.replace(target_html, new_html)
    content = content.replace(target_script, new_script)
    with open('api.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Successfully patched UI in api.py")
else:
    print("Could not find targets in api.py")
