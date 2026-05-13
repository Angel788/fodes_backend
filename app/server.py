import os
from contextlib import asynccontextmanager
from app.routers import auth, publications, comments, network, moderation, words, activity, participation
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from dotenv import load_dotenv, find_dotenv
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from app.tasks.reset import reset_semestral, reset_puntos

# Load environment variables from .env file
load_dotenv(find_dotenv())


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = BackgroundScheduler()
    # Reset semestral: 1 de febrero y 1 de agosto a las 00:00
    scheduler.add_job(reset_semestral, CronTrigger(month="2,8", day=1, hour=0, minute=0))
    # Reset de puntos: cada 30 días a las 00:00
    scheduler.add_job(reset_puntos, CronTrigger(day="1", hour="0", minute="0"))
    scheduler.start()
    print("[CRON] Scheduler iniciado")
    yield
    scheduler.shutdown()
    print("[CRON] Scheduler detenido")


limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="FODES API 2026", lifespan=lifespan)

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
app.include_router(activity.router)
app.include_router(participation.router)

if os.getenv("APP_ENV") == "development":
    from app.routers import dev
    app.include_router(dev.router)
