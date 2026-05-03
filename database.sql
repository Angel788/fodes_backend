-- FODES Database Schema
-- Reflects the actual MariaDB schema on GCP (synced 2026-05-03)

CREATE DATABASE IF NOT EXISTS FODES2;
USE FODES2;

-- ── Core tables ──────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS usuarios (
    id            INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    nombre        VARCHAR(255) NOT NULL,
    correo        VARCHAR(255) NOT NULL,
    password      VARCHAR(255) NOT NULL,
    status        ENUM('NORMAL','EN_REVISION','SUSPENDIDO','BANEADO') NOT NULL DEFAULT 'NORMAL',
    strikes_count TINYINT UNSIGNED NOT NULL DEFAULT 0,
    ban_until     DATETIME NULL DEFAULT NULL,
    UNIQUE KEY correo (correo)
);

CREATE TABLE IF NOT EXISTS categories (
    id   INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS publications (
    cid_content  VARCHAR(255) PRIMARY KEY,
    id_autor     INT NOT NULL,
    id_categoria INT NOT NULL,
    titulo       VARCHAR(255) NOT NULL,
    fecha        DATETIME NOT NULL,
    status       ENUM('NORMAL','EN_REVISION','ELIMINADA') NOT NULL DEFAULT 'NORMAL',
    report_count INT NOT NULL DEFAULT 0,
    INDEX (id_autor),
    INDEX (id_categoria),
    FOREIGN KEY (id_autor)     REFERENCES usuarios(id)   ON DELETE CASCADE,
    FOREIGN KEY (id_categoria) REFERENCES categories(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS publicacion_tags (
    id_publicacion VARCHAR(255) NOT NULL,
    nombre_tag     VARCHAR(255) NOT NULL,
    PRIMARY KEY (id_publicacion, nombre_tag),
    FOREIGN KEY (id_publicacion) REFERENCES publications(cid_content) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS comments (
    cid_content       VARCHAR(255) PRIMARY KEY,
    publication_cid   VARCHAR(255) NOT NULL,
    id_autor          INT NOT NULL,
    titulo            VARCHAR(255) NOT NULL,
    created_timestamp DATETIME NOT NULL,
    parent_cid        VARCHAR(255) NULL DEFAULT NULL,
    status            ENUM('NORMAL','EN_REVISION','ELIMINADO') NOT NULL DEFAULT 'NORMAL',
    report_count      INT UNSIGNED NOT NULL DEFAULT 0,
    INDEX (publication_cid),
    INDEX (id_autor),
    INDEX idx_comments_parent (parent_cid),
    FOREIGN KEY (publication_cid) REFERENCES publications(cid_content) ON DELETE CASCADE,
    FOREIGN KEY (id_autor)        REFERENCES usuarios(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS comentario_tags (
    id_comentario VARCHAR(255) NOT NULL,
    id_tag        INT NOT NULL,
    PRIMARY KEY (id_comentario, id_tag),
    FOREIGN KEY (id_comentario) REFERENCES comments(cid_content) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS publication_votes (
    cid_content VARCHAR(255) NOT NULL,
    id_usuario  INT NOT NULL,
    puntos      TINYINT NOT NULL CHECK (puntos BETWEEN 0 AND 5),
    PRIMARY KEY (cid_content, id_usuario),
    FOREIGN KEY (cid_content) REFERENCES publications(cid_content) ON DELETE CASCADE,
    FOREIGN KEY (id_usuario)  REFERENCES usuarios(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS comment_votes (
    cid_content VARCHAR(255) NOT NULL,
    id_usuario  INT NOT NULL,
    puntos      TINYINT NOT NULL CHECK (puntos BETWEEN 0 AND 5),
    PRIMARY KEY (cid_content, id_usuario),
    FOREIGN KEY (cid_content) REFERENCES comments(cid_content) ON DELETE CASCADE,
    FOREIGN KEY (id_usuario)  REFERENCES usuarios(id) ON DELETE CASCADE
);

-- Initial categories (must match frontend CATEGORIAS list)
INSERT IGNORE INTO categories (name) VALUES
  ('Académico'),
  ('Eventos'),
  ('Tecnología'),
  ('Ayuda');

-- ── User moderation ──────────────────────────────────────────

CREATE TABLE IF NOT EXISTS user_reports (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    reporter_id INT NOT NULL,
    reported_id INT NOT NULL,
    motivo      ENUM('spam','acoso','inapropiado','informacionFalsa') NOT NULL,
    created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY unique_user_report (reporter_id, reported_id),
    INDEX idx_reported (reported_id),
    FOREIGN KEY (reporter_id) REFERENCES usuarios(id) ON DELETE CASCADE,
    FOREIGN KEY (reported_id) REFERENCES usuarios(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS user_moderation_cases (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    target_id       INT NOT NULL,
    status          ENUM('OPEN','RESOLVED_KEEP','RESOLVED_SANCTION') NOT NULL DEFAULT 'OPEN',
    voting_deadline DATETIME NOT NULL,
    keep_count      INT UNSIGNED NOT NULL DEFAULT 0,
    sanction_count  INT UNSIGNED NOT NULL DEFAULT 0,
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resolved_at     DATETIME NULL DEFAULT NULL,
    INDEX idx_target (target_id),
    INDEX idx_status (status),
    FOREIGN KEY (target_id) REFERENCES usuarios(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS user_moderation_votes (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    case_id    INT NOT NULL,
    voter_id   INT NOT NULL,
    voto       ENUM('permanecer','sancionar') NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY unique_mod_vote (case_id, voter_id),
    FOREIGN KEY (case_id)  REFERENCES user_moderation_cases(id) ON DELETE CASCADE,
    FOREIGN KEY (voter_id) REFERENCES usuarios(id) ON DELETE CASCADE
);

-- ── Publication moderation ───────────────────────────────────

-- Note: reporter_id and voter_id are varchar(20) matching the legacy token payload
CREATE TABLE IF NOT EXISTS publication_reports (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    reporter_id     VARCHAR(20) NOT NULL,
    publication_cid VARCHAR(100) NOT NULL,
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_reporter_pub (reporter_id, publication_cid)
);

CREATE TABLE IF NOT EXISTS publication_moderation_cases (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    publication_cid VARCHAR(100) NOT NULL,
    status          ENUM('OPEN','RESOLVED_KEEP','RESOLVED_REMOVE') NOT NULL DEFAULT 'OPEN',
    keep_count      INT NOT NULL DEFAULT 0,
    remove_count    INT NOT NULL DEFAULT 0,
    voting_deadline DATETIME NOT NULL,
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resolved_at     DATETIME NULL DEFAULT NULL
);

CREATE TABLE IF NOT EXISTS publication_moderation_votes (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    case_id    INT NOT NULL,
    voter_id   VARCHAR(20) NOT NULL,
    voto       ENUM('mantener','eliminar') NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_case_voter (case_id, voter_id)
);

-- ── Content elimination tracking ─────────────────────────────

CREATE TABLE IF NOT EXISTS content_status (
    cid            VARCHAR(255) PRIMARY KEY,
    tipo           ENUM('publicacion','comentario') NOT NULL,
    status         ENUM('ELIMINADA','ELIMINADO') NOT NULL,
    deleted_reason ENUM('AUTOR_BANEADO','PUBLICACION_PADRE_ELIMINADA','MODERACION_COMUNITARIA','COMENTARIO_PADRE_ELIMINADO') NOT NULL,
    deleted_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ── Comment moderation ───────────────────────────────────────

CREATE TABLE IF NOT EXISTS comment_reports (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    comment_cid     VARCHAR(255) NOT NULL,
    reporter_id     INT NOT NULL,
    publication_cid VARCHAR(255) NOT NULL,
    motivo          ENUM('spam','acoso','inapropiado','informacionFalsa') NOT NULL,
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_comment_report (comment_cid, reporter_id),
    INDEX idx_comment (comment_cid),
    FOREIGN KEY (reporter_id)     REFERENCES usuarios(id)              ON DELETE CASCADE,
    FOREIGN KEY (publication_cid) REFERENCES publications(cid_content) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS comment_moderation_cases (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    comment_cid     VARCHAR(255) NOT NULL,
    publication_cid VARCHAR(255) NOT NULL,
    status          ENUM('OPEN','RESOLVED_KEEP','RESOLVED_REMOVE') NOT NULL DEFAULT 'OPEN',
    keep_count      INT UNSIGNED NOT NULL DEFAULT 0,
    remove_count    INT UNSIGNED NOT NULL DEFAULT 0,
    voting_deadline DATETIME NOT NULL,
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resolved_at     DATETIME NULL DEFAULT NULL,
    INDEX idx_comment_case (comment_cid),
    INDEX idx_case_status  (status),
    FOREIGN KEY (publication_cid) REFERENCES publications(cid_content) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS comment_moderation_votes (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    case_id    INT NOT NULL,
    voter_id   INT NOT NULL,
    voto       ENUM('mantener','eliminar') NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_comment_vote (case_id, voter_id),
    FOREIGN KEY (case_id)  REFERENCES comment_moderation_cases(id) ON DELETE CASCADE,
    FOREIGN KEY (voter_id) REFERENCES usuarios(id)                 ON DELETE CASCADE
);
