from fastapi import APIRouter
from fastapi.responses import RedirectResponse

router = APIRouter()

@router.get("/app")
def app_redirect():
    return RedirectResponse("/app/dashboard", status_code=303)
