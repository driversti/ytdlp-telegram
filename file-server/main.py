import logging
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from config import config
from services.file_service import file_service
from services.log_service import log_service
from services.token_service import token_service

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="YT-DLP File Server",
    description="File server for large downloads from ytdlp-telegram bot",
    version="0.1.2",
)

BASE_DIR = Path(__file__).parent
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")


def get_platform_icon(platform: str) -> str:
    """Get emoji icon for a platform."""
    icons = {
        "youtube": "📺",
        "instagram": "📷",
        "twitter": "🐦",
        "x": "🐦",
        "facebook": "📘",
        "tiktok": "🎵",
        "vimeo": "🎬",
        "reddit": "🤖",
        "twitch": "🎮",
    }
    return icons.get(platform.lower(), "📁")


templates.env.globals["get_platform_icon"] = get_platform_icon


class TokenRequest(BaseModel):
    """Request body for token generation."""

    filepath: str


class TokenResponse(BaseModel):
    """Response for token generation."""

    token: str
    url: str


class DeleteResponse(BaseModel):
    """Response for file deletion."""

    success: bool
    message: str


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Render the file browser web UI."""
    files_by_platform = file_service.list_files_by_platform()
    total_files = sum(len(files) for files in files_by_platform.values())
    total_size = sum(
        f.size_bytes for files in files_by_platform.values() for f in files
    )
    total_size_gb = total_size / (1024 * 1024 * 1024)

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "files_by_platform": files_by_platform,
            "total_files": total_files,
            "total_size_gb": total_size_gb,
            "public_url": config.public_url,
        },
    )


@app.get("/d/{token}")
async def download_file(token: str):
    """Download a file by its token."""
    file_info = file_service.get_file_by_token(token)
    if not file_info:
        raise HTTPException(status_code=404, detail="File not found or token expired")

    filepath = Path(file_info.filepath)
    if not filepath.exists():
        token_service.delete_token(token)
        raise HTTPException(status_code=404, detail="File no longer exists")

    return FileResponse(
        path=filepath,
        filename=file_info.filename,
        media_type="application/octet-stream",
    )


@app.get("/api/files")
async def list_files():
    """List all files with their tokens."""
    files = file_service.list_files()
    return [
        {
            "filename": f.filename,
            "filepath": f.filepath,
            "size_mb": round(f.size_mb, 2),
            "platform": f.platform,
            "created_at": f.created_at.isoformat(),
            "token": f.token,
            "download_url": f"{config.public_url}/d/{f.token}" if f.token else None,
        }
        for f in files
    ]


@app.post("/api/tokens", response_model=TokenResponse)
async def generate_token(request: TokenRequest):
    """Generate a download token for a file."""
    token = file_service.get_or_create_token(request.filepath)
    if not token:
        raise HTTPException(status_code=400, detail="Invalid or inaccessible file path")

    return TokenResponse(
        token=token,
        url=f"{config.public_url}/d/{token}",
    )


@app.delete("/api/files/{token}", response_model=DeleteResponse)
async def delete_file(token: str):
    """Delete a file by its token."""
    success = file_service.delete_file_by_token(token)
    if success:
        return DeleteResponse(success=True, message="File deleted successfully")
    else:
        raise HTTPException(status_code=404, detail="File not found or already deleted")


@app.post("/api/cleanup")
async def cleanup_orphaned():
    """Clean up tokens for files that no longer exist."""
    removed = token_service.cleanup_orphaned_tokens()
    return {"removed": removed}


@app.get("/logs", response_class=HTMLResponse)
async def logs_page(request: Request):
    """Render the logs viewer web UI."""
    stats = log_service.get_log_stats()
    return templates.TemplateResponse(
        "logs.html",
        {
            "request": request,
            "stats": stats.to_dict(),
        },
    )


@app.get("/api/logs")
async def get_logs(
    lines: int = 200,
    level: str | None = None,
    search: str | None = None,
):
    """Get log entries as JSON for polling."""
    entries = log_service.read_logs(lines=lines, level_filter=level, search=search)
    stats = log_service.get_log_stats()
    return {
        "entries": [e.to_dict() for e in entries],
        "stats": stats.to_dict(),
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=config.port,
        reload=False,
    )
