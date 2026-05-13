from datetime import datetime
from sqlalchemy import text


def reset_semestral():
    """
    Corre el 1 de febrero y el 1 de agosto a las 00:00.
    Elimina todo el contenido del semestre anterior:
    publicaciones, comentarios y sus tablas relacionadas.
    Los usuarios, strikes, bolsa de palabras y word_votes se mantienen.
    Aprovecha para suspender indefinidamente a alumnos con más de 10 semestres.
    """
    from app.db.database import engine
    with engine.connect() as conn:
        conn.execute(text("SET FOREIGN_KEY_CHECKS = 0"))

        tablas = [
            "comment_moderation_votes",
            "comment_moderation_cases",
            "publication_moderation_votes",
            "publication_moderation_cases",
            "comment_reports",
            "publication_reports",
            "user_reports",
            "user_moderation_votes",
            "user_moderation_cases",
            "comment_votes",
            "publication_votes",
            "comentario_tags",
            "publicacion_tags",
            "participation_log",
            "comments",
            "publications",
        ]
        for tabla in tablas:
            conn.execute(text(f"TRUNCATE TABLE {tabla}"))

        # Suspender indefinidamente alumnos que superaron 10 semestres (5 años)
        anio_actual = datetime.now().year
        conn.execute(text("""
            UPDATE usuarios
            SET status = 'SUSPENDIDO', ban_until = NULL
            WHERE status NOT IN ('BANEADO', 'SUSPENDIDO')
              AND FLOOR(id / 1000000) + 5 <= :anio
        """), {"anio": anio_actual})

        conn.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
        conn.commit()

    print(f"[CRON] Reset semestral completado — {datetime.now()}")


def reset_puntos():
    """
    Corre cada 30 días.
    Resetea los puntos de participación de todos los usuarios a 0.
    """
    from app.db.database import engine
    with engine.connect() as conn:
        conn.execute(text("UPDATE usuarios SET puntos_participacion = 0"))
        conn.commit()

    print(f"[CRON] Reset de puntos completado — {datetime.now()}")
