from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import users, items
from app.core.config import settings

app = FastAPI(
    title=settings.app_name,
    description="A FastAPI backend for SP Website",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this properly for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(users.router)
app.include_router(items.router)

@app.get("/")
async def root():
    return {"message": "Welcome to SP Website API"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
