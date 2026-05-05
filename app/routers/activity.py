from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.db.database import get_db
from app.dependencies import verifyActiveSession

router = APIRouter(prefix="/activity", tags=["Activity"])

PERIODOS = {
    "24h": timedelta(hours=24),
    "7d":  timedelta(days=7),
    "1m":  timedelta(days=30),
}


def _bounds(periodo: str):
    delta = PERIODOS[periodo]
    now   = datetime.utcnow()
    end   = now
    start = now - delta
    prev_end   = start
    prev_start = start - delta
    return start, end, prev_start, prev_end


def _metrics(db: Session, start: datetime, end: datetime) -> dict:
    n_pub = db.execute(text("""
        SELECT COUNT(*) FROM publications
        WHERE fecha BETWEEN :s AND :e
    """), {"s": start, "e": end}).scalar() or 0

    n_com = db.execute(text("""
        SELECT COUNT(*) FROM comments
        WHERE created_timestamp BETWEEN :s AND :e
    """), {"s": start, "e": end}).scalar() or 0

    promedio = db.execute(text("""
        SELECT AVG(puntos) FROM publication_votes
        WHERE voted_at BETWEEN :s AND :e
    """), {"s": start, "e": end}).scalar()
    promedio = round(float(promedio), 2) if promedio else None

    tr = db.execute(text("""
        SELECT AVG(TIMESTAMPDIFF(MINUTE, p.fecha, fc.min_ts))
        FROM publications p
        JOIN (
            SELECT publication_cid, MIN(created_timestamp) AS min_ts
            FROM comments
            GROUP BY publication_cid
        ) fc ON fc.publication_cid = p.cid_content
        WHERE p.fecha BETWEEN :s AND :e
    """), {"s": start, "e": end}).scalar()
    tr = round(float(tr), 1) if tr else None

    tres = db.execute(text("""
        SELECT AVG(TIMESTAMPDIFF(MINUTE, p.fecha, fv.min_voted))
        FROM publications p
        JOIN (
            SELECT cid_content, MIN(voted_at) AS min_voted
            FROM publication_votes
            GROUP BY cid_content
        ) fv ON fv.cid_content = p.cid_content
        WHERE p.fecha BETWEEN :s AND :e
    """), {"s": start, "e": end}).scalar()
    tres = round(float(tres), 1) if tres else None

    return {
        "n_publicaciones":      n_pub,
        "n_comentarios":        n_com,
        "promedio_calificacion": promedio,
        "tr_minutos":           tr,
        "tres_minutos":         tres,
    }


@router.get("")
async def get_activity(
    periodo: str = Query(default="7d", pattern="^(24h|7d|1m)$"),
    db: Session = Depends(get_db),
    id_user: str = Depends(verifyActiveSession),
):
    start, end, prev_start, prev_end = _bounds(periodo)

    return {
        "status":   "success",
        "periodo":  periodo,
        "actual":   _metrics(db, start, end),
        "anterior": _metrics(db, prev_start, prev_end),
    }
