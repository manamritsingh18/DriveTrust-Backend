from fastapi import FastAPI
from app.routes.uploads import router as upload_router

app = FastAPI(
    title="DriveTrust Backend",
    version="1.0.0"
)

# Register routers
app.include_router(upload_router)


@app.get("/")
def root():
    return {
        "message": "DriveTrust Backend Running 🚗"
    }


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "message": "Backend is running"
    }