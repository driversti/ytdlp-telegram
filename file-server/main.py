import logging
import os
import secrets
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException, Request, Form
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from starlette.middleware.sessions import SessionMiddleware

from config import config
from services.file_service import file_service
from services.log_service import log_service
from services.token_service import token_service
from services.user_service import user_service
from services.telegram_service import telegram_service

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="YT-DLP File Server",
    description="File server for large downloads from ytdlp-telegram bot",
    version="0.1.5",
)

# Session middleware for admin authentication
# Generate a random secret key if not provided (will change on restart)
SESSION_SECRET = os.getenv("SESSION_SECRET", secrets.token_hex(32))
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET)

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


# ============== Admin Routes ==============

def is_admin_authenticated(request: Request) -> bool:
    """Check if the admin is authenticated via session."""
    return request.session.get("admin_authenticated", False)


def get_env_allowed_user_ids() -> set[int]:
    """Get allowed user IDs from environment variable."""
    allowed_ids_str = os.getenv("ALLOWED_USER_IDS", "")
    if not allowed_ids_str:
        return set()
    return {int(uid.strip()) for uid in allowed_ids_str.split(",") if uid.strip()}


@app.get("/admin/login", response_class=HTMLResponse)
async def admin_login_page(request: Request):
    """Render the admin login page."""
    if is_admin_authenticated(request):
        return RedirectResponse(url="/admin", status_code=303)

    if not config.admin_password:
        return templates.TemplateResponse(
            "admin_login.html",
            {
                "request": request,
                "error": "Admin password not configured. Set ADMIN_PASSWORD environment variable.",
            },
        )

    return templates.TemplateResponse(
        "admin_login.html",
        {"request": request, "error": None},
    )


@app.post("/admin/login")
async def admin_login(request: Request, password: str = Form(...)):
    """Handle admin login form submission."""
    if not config.admin_password:
        return RedirectResponse(url="/admin/login", status_code=303)

    if password == config.admin_password:
        request.session["admin_authenticated"] = True
        return RedirectResponse(url="/admin", status_code=303)

    return templates.TemplateResponse(
        "admin_login.html",
        {"request": request, "error": "Invalid password"},
        status_code=401,
    )


@app.get("/admin/logout")
async def admin_logout(request: Request):
    """Handle admin logout."""
    request.session.clear()
    return RedirectResponse(url="/admin/login", status_code=303)


@app.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    """Render the admin dashboard."""
    if not is_admin_authenticated(request):
        return RedirectResponse(url="/admin/login", status_code=303)

    # Get users from database
    db_approved_users = user_service.get_approved_users()
    pending_requests = user_service.get_pending_requests()
    denied_users = user_service.get_denied_users()

    # Get env-based allowed users
    env_user_ids = get_env_allowed_user_ids()

    # Combine for display (env users shown separately)
    return templates.TemplateResponse(
        "admin.html",
        {
            "request": request,
            "env_user_ids": sorted(env_user_ids),
            "db_approved_users": db_approved_users,
            "pending_requests": pending_requests,
            "denied_users": denied_users,
        },
    )


class AddUserRequest(BaseModel):
    """Request body for adding a user."""
    telegram_id: int


@app.post("/api/admin/users")
async def api_add_user(request: Request, data: AddUserRequest):
    """Add a user via API."""
    if not is_admin_authenticated(request):
        raise HTTPException(status_code=401, detail="Not authenticated")

    # Check if user is already in env whitelist
    env_user_ids = get_env_allowed_user_ids()
    if data.telegram_id in env_user_ids:
        raise HTTPException(status_code=400, detail="User is already in environment whitelist")

    # Check if user already exists in DB
    existing = user_service.get_user(data.telegram_id)
    if existing and existing.status == "approved":
        raise HTTPException(status_code=400, detail="User is already approved")

    success = user_service.add_user(data.telegram_id)
    if success:
        return {"success": True, "message": "User added successfully"}
    else:
        raise HTTPException(status_code=400, detail="User already exists in database")


@app.delete("/api/admin/users/{telegram_id}")
async def api_remove_user(request: Request, telegram_id: int):
    """Remove a user from the database."""
    if not is_admin_authenticated(request):
        raise HTTPException(status_code=401, detail="Not authenticated")

    # Check if user is in env whitelist (can't remove those)
    env_user_ids = get_env_allowed_user_ids()
    if telegram_id in env_user_ids:
        raise HTTPException(status_code=400, detail="Cannot remove env-based users. Edit ALLOWED_USER_IDS instead.")

    success = user_service.remove_user(telegram_id)
    if success:
        return {"success": True, "message": "User removed successfully"}
    else:
        raise HTTPException(status_code=404, detail="User not found")


@app.post("/api/admin/users/{telegram_id}/approve")
async def api_approve_user(request: Request, telegram_id: int):
    """Approve a user's access request."""
    if not is_admin_authenticated(request):
        raise HTTPException(status_code=401, detail="Not authenticated")

    success = user_service.approve_user(telegram_id)
    if success:
        # Notify the user via Telegram
        await telegram_service.notify_user_approved(telegram_id)
        return {"success": True, "message": "User approved successfully"}
    else:
        raise HTTPException(status_code=404, detail="User not found or already approved")


@app.post("/api/admin/users/{telegram_id}/deny")
async def api_deny_user(request: Request, telegram_id: int):
    """Deny a user's access request."""
    if not is_admin_authenticated(request):
        raise HTTPException(status_code=401, detail="Not authenticated")

    success = user_service.deny_user(telegram_id)
    if success:
        # Notify the user via Telegram
        await telegram_service.notify_user_denied(telegram_id)
        return {"success": True, "message": "User denied successfully"}
    else:
        raise HTTPException(status_code=404, detail="User not found")


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=config.port,
        reload=False,
    )
