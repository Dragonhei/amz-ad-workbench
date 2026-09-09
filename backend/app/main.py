"""应用入口。"""
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .db import Base, engine
from .models import *          # noqa: F401,F403  建表需要
from .routers import admin, analysis, bi, comments, ingest, inventory, kb, launch, notify
from .seed import seed_all

app = FastAPI(title="AI 广告分析工作台", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

app.include_router(ingest.router)
app.include_router(bi.router)
app.include_router(analysis.router)
app.include_router(inventory.router)
app.include_router(kb.router)
app.include_router(launch.router)
app.include_router(comments.router)
app.include_router(notify.router)
app.include_router(admin.router)

DIST = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                    "frontend", "dist")


@app.on_event("startup")
def on_start():
    Base.metadata.create_all(bind=engine)
    seed_all()


@app.get("/api/health")
def health():
    return {"ok": True, "service": "amz-ad-workbench", "version": "0.1.0"}


if os.path.isdir(DIST):
    app.mount("/assets", StaticFiles(directory=os.path.join(DIST, "assets")), name="assets")

    @app.get("/{full_path:path}")
    def spa(full_path: str):
        idx = os.path.join(DIST, "index.html")
        if os.path.exists(idx):
            return FileResponse(idx)
        return {"message": "前端未构建，请执行 npm run build"}
