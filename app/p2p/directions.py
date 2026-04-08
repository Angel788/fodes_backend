import redis
import os
from dotenv import load_dotenv, find_dotenv

# Load .env
load_dotenv(find_dotenv())

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = int(os.getenv("REDIS_DB", 0))
BOOTSTRAP_DIR = os.getenv("BOOTSTRAP_DIR", "../NETWORK")
PSK_PATH = os.getenv("PSK_PATH", "psk.key")

redis_client = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    db=REDIS_DB,
    decode_responses=True
)


def getP2PDirection():
    """Retrieves the bootstrap node address from Redis."""
    return BOOTSTRAP_DIR


def getP2PPSK():
    """
    Reads the PSK from PSK_PATH or fallback to swarm.key.
    """
    # 1. Try path from .env
    if os.path.exists(PSK_PATH):
        with open(PSK_PATH, "r") as f:
            return f.read().strip()

    # 2. Try inside BOOTSTRAP_DIR
    path_in_bootstrap = os.path.join(BOOTSTRAP_DIR, "swarm.key")
    if os.path.exists(path_in_bootstrap):
        with open(path_in_bootstrap, "r") as f:
            return f.read().strip()

    # 3. Try swarm.key in current root
    if os.path.exists("swarm.key"):
        with open("swarm.key", "r") as f:
            return f.read().strip()

    # 4. Deep fallback
    fallback_path = os.path.join(os.path.dirname(
        __file__), "..", "..", "..", "NETWORK", "swarm.key")
    if os.path.exists(fallback_path):
        with open(fallback_path, "r") as f:
            return f.read().strip()

    return None

    return None
