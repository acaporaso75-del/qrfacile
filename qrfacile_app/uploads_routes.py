import os
from fastapi import APIRouter, HTTPException, Path
from fastapi.responses import FileResponse

router = APIRouter()

UPLOADS_DIR = os.getenv("UPLOADS_DIR", os.path.join(os.getenv("APP_ROOT", "/opt/qrfacile"), "uploads"))

def _serve_upload(path: str):
    if ".." in path or path.startswith("/"):
        raise HTTPException(400, "Bad path")

    abs_path = os.path.normpath(os.path.join(UPLOADS_DIR, path))
    base = os.path.normpath(UPLOADS_DIR)

    if not abs_path.startswith(base):
        raise HTTPException(400, "Bad path")

    if not os.path.exists(abs_path):
        raise HTTPException(404, "Not found")

    return FileResponse(abs_path)

@router.get("/uploads/{path:path}")
def uploads_get(path: str = Path(...)):
    return _serve_upload(path)

@router.head("/uploads/{path:path}")
def uploads_head(path: str = Path(...)):
    return _serve_upload(path)
