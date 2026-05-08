import os

with open("api.py", "r", encoding="utf-8") as f:
    api_content = f.read()

# Remove the block:
block = """
if __name__ == "__main__":
    uvicorn.run(app, host=config.API_HOST, port=config.API_PORT)
"""

if block in api_content:
    api_content = api_content.replace(block, "")
    api_content = api_content + "\n" + block
    
    with open("api.py", "w", encoding="utf-8") as f:
        f.write(api_content)
    print("Fixed endpoint order!")
else:
    print("Block not found!")
