from fastapi import FastAPI
from fastapi.responses import JSONResponse

# FastAPI application for Cloud Run deployment v1.0
app = FastAPI(title="FastAPI Demo App")

@app.get("/")
async def root():
    return {"message": "Hello World", "version": "1.0"}

@app.get("/health")
async def health_check():
    return JSONResponse(
        status_code=200,
        content={"status": "healthy"}
    ) 