"""启动后端服务：python run.py  →  http://127.0.0.1:8000"""
import os
import sys

import uvicorn

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("app.main:app", host="127.0.0.1", port=port, log_level="info")
