from fastapi import APIRouter, Request, HTTPException, Depends
from slowapi import Limiter
from slowapi.util import get_remote_address
from app.p2p.directions import getP2PDirection, getP2PPSK
from app.auth.auth import verifySession

router = APIRouter(tags=["Network"])
limiter = Limiter(key_func=get_remote_address)


@router.get("/network/bootstrap-info")
@limiter.limit("5/minute")
async def get_bootstrap_info(
    request: Request,
    id_user: int = Depends(verifySession)
):
    """
    Returns the current P2P bootstrap node multiaddr and the swarm PSK.
    Essential for new nodes joining the network.
    """
    bootstrap_node = getP2PDirection()
    psk = getP2PPSK()

    if not bootstrap_node:
        raise HTTPException(
            status_code=404, detail="Bootstrap node not found in Redis")

    return {
        "bootstrap_node": bootstrap_node,
        "psk": psk,
        "status": "online" if bootstrap_node else "offline"
    }


@router.get("/directionBoostrapNode")
@limiter.limit("5/minute")
async def get_direction_bootstrap_node(
    request: Request,
    id_user: int = Depends(verifySession)
):
    """
    Legacy endpoint to get the bootstrap node address only.
    """
    return {
        "BoostrapNode": getP2PDirection()
    }
