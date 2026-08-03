from fastapi import APIRouter, HTTPException, Path
from fastapi.responses import FileResponse
from qrfacile_app.services.storage import asset_absolute_path

router = APIRouter()

def _serve_upload(path: str):
    try:
        abs_path = asset_absolute_path(path)
    except ValueError:
        raise HTTPException(400, "Percorso file non valido")
    if not abs_path.is_file():
        raise HTTPException(404, "Immagine non disponibile")
    return FileResponse(str(abs_path), headers={"Cache-Control": "public, max-age=3600, must-revalidate"})

@router.get("/uploads/{path:path}")
def uploads_get(path: str = Path(...)):
    return _serve_upload(path)

@router.head("/uploads/{path:path}")
def uploads_head(path: str = Path(...)):
    return _serve_upload(path)
