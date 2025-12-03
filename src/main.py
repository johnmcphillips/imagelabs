from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from starlette import status

app = FastAPI(title="Image Thumbnail Service", version="0.1.0")

@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}

@app.get("/")
def root() -> dict:
    return {"message": "Testing"}