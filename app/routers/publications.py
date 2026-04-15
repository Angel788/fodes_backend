from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, Request, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.db.database import get_db
from app.auth.auth import verifySession
from app.p2p.cid import generateCid
from app.interfaces.PublicationsCreate import PublicationCreate
from app.interfaces.PublicationsVote import PublicationVote
from app.interfaces.RatingBatchConsult import RatingBatchConsult

router = APIRouter(prefix="/publications", tags=["Publications"])
limiter = Limiter(key_func=get_remote_address)


@router.post("")
@limiter.limit("3/minute")
async def set_publication(
    request: Request,
    pub: PublicationCreate,
    db: Session = Depends(get_db),
    id_autor: int = Depends(verifySession)
):
    """
    Registers a new publication metadata in the database and generates a CID.
    Requires authentication.
    - **title**: Publication title.
    - **content**: Markdown or text content.
    - **tags**: List of relevant tags.
    - **category**: Publication category (must exist in categories table).
    """
    try:
        # Get author name for CID generation
        query_user = text("SELECT nombre FROM usuarios WHERE id = :id")
        user_result = db.execute(query_user, {"id": id_autor}).fetchone()

        if not user_result:
            raise HTTPException(
                status_code=404, detail="Usuario no encontrado")

        nombre_autor = user_result[0]

        # Verify category exists
        query_get_cat = text("SELECT id FROM categories WHERE name = :name")
        cat_result = db.execute(
            query_get_cat, {"name": pub.category}).fetchone()

        if not cat_result:
            raise HTTPException(
                status_code=400, detail=f"La categoría '{pub.category}' no existe.")

        id_categoria = cat_result[0]
        curr_date = datetime.now()

        # Usar el CID generado por el gateway P2P
        cid_content = pub.cid_content

        # Index publication metadata
        query_pub = text("""
            INSERT IGNORE INTO publications (cid_content, id_autor, id_categoria, titulo, fecha)
            VALUES (:cid, :autor, :cat_id, :titulo, :fecha)
        """)
        db.execute(query_pub, {
            "cid": cid_content,
            "autor": id_autor,
            "cat_id": id_categoria,
            "titulo": pub.title,
            "fecha": curr_date
        })

        # Index tags
        if pub.tags:
            query_tag = text("""
                INSERT IGNORE INTO publicacion_tags (id_publicacion, nombre_tag) 
                VALUES (:cid, :tag_str)
            """)
            for tag_name in pub.tags:
                db.execute(
                    query_tag, {"cid": cid_content, "tag_str": tag_name})

        db.commit()

        return {
            "status": "success",
            "message": "Publicación indexada correctamente",
            "data": {
                "cid_content": cid_content,
                "content": cid_payload
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500, detail=f"Error al registrar la publicación: {str(e)}")


@router.get("/search-cids")
async def search_publications_cids(
    cid: Optional[str] = Query(None),
    categoria: Optional[str] = Query(None),
    tags: Optional[List[str]] = Query(None),
    db: Session = Depends(get_db),
    id_user: int = Depends(verifySession)
):
    """
    Search for publication CIDs based on multiple filters.
    Requires authentication.
    - **cid**: Exact CID match.
    - **categoria**: Category name filter.
    - **tags**: List of tags (OR logic).
    """
    try:
        base_query = "SELECT DISTINCT p.cid_content FROM publications p"
        joins = []
        conditions = []
        params = {}

        if categoria:
            joins.append("JOIN categories c ON p.id_categoria = c.id")
            conditions.append("c.name = :categoria")
            params["categoria"] = categoria

        if tags:
            joins.append(
                "JOIN publicacion_tags pt ON p.cid_content = pt.id_publicacion")
            conditions.append("pt.nombre_tag IN :tags_list")
            params["tags_list"] = tuple(tags)

        if cid:
            conditions.append("p.cid_content = :cid")
            params["cid"] = cid

        final_query = base_query
        if joins:
            final_query += " " + " ".join(joins)
        if conditions:
            final_query += " WHERE " + " AND ".join(conditions)

        result = db.execute(text(final_query), params).fetchall()
        cids_only = [row[0] for row in result]

        return {
            "status": "success",
            "count": len(cids_only),
            "cids": cids_only
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error en la búsqueda: {str(e)}")


@router.post("/vote")
@limiter.limit("10/minute")
async def vote_publication(
    request: Request,
    vote_data: PublicationVote,
    db: Session = Depends(get_db),
    id_user: int = Depends(verifySession)
):
    """
    Submit or update a 0-5 rating for a publication.
    Requires authentication.
    - **cid_content**: Target publication CID.
    - **vote**: Rating points (0 to 5).
    """
    try:
        # Use ON DUPLICATE KEY UPDATE to allow changing the vote
        query_vote = text("""
            INSERT INTO publication_votes (cid_content, id_usuario, puntos)
            VALUES (:cid_content, :id_usuario, :puntos)
            ON DUPLICATE KEY UPDATE puntos = VALUES(puntos)
        """)
        db.execute(query_vote, {
            "cid_content": vote_data.cid_content,
            "id_usuario": id_user,
            "puntos": vote_data.vote
        })

        db.commit()
        return {
            "status": "success",
            "message": "Voto registrado correctamente (0-5)"
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500, detail=f"Error al registrar el voto: {str(e)}")


@router.post("/rating")
@limiter.limit("20/minute")
async def get_publications_rating(
    request: Request,
    batch: RatingBatchConsult,
    db: Session = Depends(get_db),
    id_user: int = Depends(verifySession)
):
    """
    Batch retrieve average ratings and total votes for a list of publications.
    - **cids**: Array of publication CIDs.
    """
    try:
        if not batch.cids:
            raise HTTPException(status_code=400, detail="No CIDs provided")

        # Group by CID to calculate averages in one go
        query = text("""
            SELECT cid_content, AVG(puntos) as average, COUNT(*) as count 
            FROM publication_votes 
            WHERE cid_content IN :cid_list
            GROUP BY cid_content
        """)
        result = db.execute(query, {"cid_list": tuple(batch.cids)}).fetchall()

        ratings = {row.cid_content: {
            "average_rating": float(row.average) if row.average else 0,
            "total_votes": row.count
        } for row in result}

        # Ensure all requested CIDs are in the response even if they have no votes
        for cid in batch.cids:
            if cid not in ratings:
                ratings[cid] = {"average_rating": 0, "total_votes": 0}

        return {
            "status": "success",
            "ratings": ratings
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
