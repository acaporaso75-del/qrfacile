from fastapi import APIRouter, HTTPException, Path, Request
from fastapi.responses import FileResponse
from qrfacile_app.services.storage import asset_absolute_path

router = APIRouter()

def _serve_upload(path: str, *, versioned: bool = False):
    try:
        abs_path = asset_absolute_path(path)
    except ValueError:
        raise HTTPException(400, "Percorso file non valido")
    if not abs_path.is_file():
        raise HTTPException(404, "Immagine non disponibile")
    cache_control = "public, max-age=31536000, immutable" if versioned else "public, max-age=3600, must-revalidate"
    return FileResponse(str(abs_path), headers={"Cache-Control": cache_control})

@router.get("/uploads/{path:path}")
def uploads_get(request: Request, path: str = Path(...)):
    return _serve_upload(path, versioned=bool(request.query_params.get("v")))

@router.head("/uploads/{path:path}")
def uploads_head(request: Request, path: str = Path(...)):
    return _serve_upload(path, versioned=bool(request.query_params.get("v")))
