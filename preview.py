from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse

app = FastAPI(title="올영양소 V10.1 Redirect")
TARGET = "https://allnutrients-v10-options.onrender.com"

@app.api_route("/{path:path}", methods=["GET","HEAD","POST","PUT","PATCH","DELETE","OPTIONS"])
async def redirect_all(request: Request, path: str):
    query = ("?" + request.url.query) if request.url.query else ""
    return RedirectResponse(f"{TARGET}/{path}{query}", status_code=307)
