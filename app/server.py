import os
from app.routers import auth, publications, comments, network, moderation, words
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from dotenv import load_dotenv, find_dotenv

# Load environment variables from .env file
load_dotenv(find_dotenv())


limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="FODES API 2026")

# Setup Limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Setup CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

# Include Routers
app.include_router(auth.router)
app.include_router(publications.router)
app.include_router(comments.router)
app.include_router(network.router)
app.include_router(moderation.router)
app.include_router(words.router)

if os.getenv("APP_ENV") == "development":
    from app.routers import dev
    app.include_router(dev.router)
