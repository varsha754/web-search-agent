import requests

print("Testing /api/chat_stream...")
try:
    with requests.get("http://localhost:8000/api/chat_stream?query=what+is+fsi", stream=True) as r:
        for line in r.iter_lines():
            if line:
                print(line.decode('utf-8'))
except Exception as e:
    print("Error:", e)
