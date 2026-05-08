import sys

with open('api.py', 'r', encoding='utf-8') as f:
    content = f.read()

target = '@app.get("/api/stats")'

new_endpoint = """@app.get("/api/extract")
async def extract(
    url: str = Query(..., min_length=5),
    query: str = Query(..., min_length=1)
):
    \"\"\"Extract exactly what is asked for from a given URL\"\"\"
    result = agent.extract_from_url(url, query)
    if result.get('success'):
        return result
    else:
        raise HTTPException(status_code=400, detail=result.get('error', 'Unknown error'))


"""

if target in content:
    content = content.replace(target, new_endpoint + target)
    with open('api.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Successfully patched api.py")
else:
    print("Could not find target in api.py")
