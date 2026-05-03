from datetime import datetime
from fastapi import APIRouter, Depends, Request, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.db.database import get_db
from app.auth.auth import verifySession
from app.dependencies import verifyActiveSession
from app.p2p.cid import generateCid
from app.interfaces.CommentCreate import CommentCreate
from app.interfaces.CommentVote import CommentVote
from app.interfaces.RatingBatchConsult import RatingBatchConsult

router = APIRouter(prefix="/comments", tags=["Comments"])
limiter = Limiter(key_func=get_remote_address)


@router.post("")
@limiter.limit("5/minute")
async def set_comment(
    request: Request,
    comment: CommentCreate,
    db: Session = Depends(get_db),
    id_autor: str = Depends(verifyActiveSession)
):
    """
    Registers a new comment metadata and links it to a publication CID.
    Requires authentication.
    - **titulo**: Comment title.
    - **publication_cid**: The CID of the publication this comment belongs to.
    - **contenido**: Comment body.
    - **tags**: Optional list of tag IDs.
    """
    try:
        # Get author name for CID generation
        query_user = text("SELECT nombre FROM usuarios WHERE id = :id")
        user_result = db.execute(query_user, {"id": id_autor}).fetchone()

        if not user_result:
            raise HTTPException(
                status_code=404, detail="Usuario no encontrado")

        nombre_autor = user_result[0]
        fecha_actual = datetime.now()

        # Generate CID for the comment
        cid_payload = {
            "title": comment.titulo,
            "publication_cid": comment.publication_cid,
            "content": comment.contenido,
            "author": nombre_autor,
            "date": fecha_actual.isoformat()
        }
        cid_generated = generateCid(cid_payload)

        # Index comment metadata
        query_comment = text("""
            INSERT IGNORE INTO comments
                (cid_content, publication_cid, id_autor, titulo, created_timestamp, parent_cid)
            VALUES (:cid, :pub_cid, :autor, :titulo, :fecha, :parent_cid)
        """)
        db.execute(query_comment, {
            "cid": cid_generated,
            "pub_cid": comment.publication_cid,
            "autor": id_autor,
            "titulo": comment.titulo,
            "fecha": fecha_actual,
            "parent_cid": comment.parent_cid,
        })

        # Link tags to comment
        if comment.tags:
            query_tag = text(
                "INSERT IGNORE INTO comentario_tags (id_comentario, id_tag) VALUES (:cid, :tag_id)")
            for tag_id in comment.tags:
                db.execute(query_tag, {"cid": cid_generated, "tag_id": tag_id})

        db.commit()

        return {
            "status": "success",
            "message": "Comentario registrado con éxito",
            "cid": cid_generated,
            "content": cid_payload
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/publication/{publication_cid}")
async def get_publication_comments(
    publication_cid: str,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
    id_user: str = Depends(verifySession)
):
    """
    Retrieves all comment CIDs associated with a specific publication.
    - **publication_cid**: The CID of the target publication.
    - **limit**: Max results to return.
    - **offset**: Pagination offset.
    """
    try:
        query = text("""
            SELECT cid_content 
            FROM comments 
            WHERE publication_cid = :pub_cid 
            ORDER BY created_timestamp ASC 
            LIMIT :limit OFFSET :offset
        """)

        result = db.execute(query, {
            "pub_cid": publication_cid,
            "limit": limit,
            "offset": offset
        }).fetchall()

        return {
            "status": "success",
            "data": [row[0] for row in result]
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error al obtener los comentarios: {str(e)}")


@router.post("/vote")
@limiter.limit("10/minute")
async def vote_comment(
    request: Request,
    vote_data: CommentVote,
    db: Session = Depends(get_db),
    id_user: str = Depends(verifyActiveSession)
):
    """
    Submit or update a 0-5 rating for a comment.
    Requires authentication.
    - **cid_content**: Target comment CID.
    - **vote**: Rating points (0 to 5).
    """
    try:
        query_vote = text("""
            INSERT INTO comment_votes (cid_content, id_usuario, puntos)
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
            "message": "Voto de comentario registrado correctamente (0-5)"
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500, detail=f"Error al registrar el voto: {str(e)}")


@router.post("/moderation-status")
@limiter.limit("20/minute")
async def get_comments_moderation_status(
    request: Request,
    batch: RatingBatchConsult,
    db: Session = Depends(get_db),
    id_user: str = Depends(verifySession)
):
    """
    Batch retrieve moderation status for a list of comment CIDs.
    Returns statuses: NORMAL | EN_REVISION | ELIMINADO
    """
    if not batch.cids:
        return {"status": "success", "statuses": {}}

    cids_tuple = tuple(batch.cids) if len(batch.cids) > 1 else (batch.cids[0],)

    # Eliminated CIDs from content_status
    elim_rows = db.execute(text("""
        SELECT cid FROM content_status WHERE cid IN :cids AND tipo='comentario'
    """), {"cids": cids_tuple}).fetchall()
    eliminated = {r.cid for r in elim_rows}

    # EN_REVISION CIDs from comment_moderation_cases
    revision_rows = db.execute(text("""
        SELECT comment_cid FROM comment_moderation_cases
        WHERE comment_cid IN :cids AND status='OPEN'
    """), {"cids": cids_tuple}).fetchall()
    en_revision = {r.comment_cid for r in revision_rows}

    statuses = {}
    for cid in batch.cids:
        if cid in eliminated:
            statuses[cid] = 'ELIMINADO'
        elif cid in en_revision:
            statuses[cid] = 'EN_REVISION'
        else:
            statuses[cid] = 'NORMAL'

    return {"status": "success", "statuses": statuses}


@router.post("/rating")
@limiter.limit("20/minute")
async def get_comments_rating(
    request: Request,
    batch: RatingBatchConsult,
    db: Session = Depends(get_db),
    id_user: str = Depends(verifySession)
):
    """
    Batch retrieve average ratings and total votes for a list of comments.
    - **cids**: Array of comment CIDs.
    """
    try:
        if not batch.cids:
            raise HTTPException(status_code=400, detail="No CIDs provided")

        query = text("""
            SELECT cid_content, AVG(puntos) as average, COUNT(*) as count 
            FROM comment_votes 
            WHERE cid_content IN :cid_list
            GROUP BY cid_content
        """)
        result = db.execute(query, {"cid_list": tuple(batch.cids)}).fetchall()

        ratings = {row.cid_content: {
            "average_rating": float(row.average) if row.average else 0,
            "total_votes": row.count
        } for row in result}

        # Ensure all requested CIDs are in the response
        for cid in batch.cids:
            if cid not in ratings:
                ratings[cid] = {"average_rating": 0, "total_votes": 0}

        return {
            "status": "success",
            "ratings": ratings
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
