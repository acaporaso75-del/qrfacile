from urllib.parse import parse_qs

from fastapi import APIRouter, HTTPException, Path, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from qrfacile_app.services.storage import asset_absolute_path

router = APIRouter()


def _cache_control(versioned: bool) -> str:
    return "public, max-age=31536000, immutable" if versioned else "public, max-age=3600, must-revalidate"


class VersionedUploadStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope):
        response = await super().get_response(path, scope)
        query = parse_qs(scope.get("query_string", b"").decode("latin-1"))
        response.headers["Cache-Control"] = _cache_control(bool(query.get("v")))
        return response


def _serve_upload(path: str, *, versioned: bool = False):
    try:
        abs_path = asset_absolute_path(path)
    except ValueError:
        raise HTTPException(400, "Percorso file non valido")
    if not abs_path.is_file():
        raise HTTPException(404, "Immagine non disponibile")
    return FileResponse(str(abs_path), headers={"Cache-Control": _cache_control(versioned)})

@router.get("/uploads/{path:path}")
def uploads_get(request: Request, path: str = Path(...)):
    return _serve_upload(path, versioned=bool(request.query_params.get("v")))

@router.head("/uploads/{path:path}")
def uploads_head(request: Request, path: str = Path(...)):
    return _serve_upload(path, versioned=bool(request.query_params.get("v")))
