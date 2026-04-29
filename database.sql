-- FODES Database Schema
-- Reflects the actual MariaDB schema on GCP

CREATE DATABASE IF NOT EXISTS FODES2;
USE FODES2;

-- Table for user management
CREATE TABLE IF NOT EXISTS usuarios (
    id       INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    nombre   VARCHAR(255) NOT NULL,
    correo   VARCHAR(255) NOT NULL,
    password VARCHAR(255) NOT NULL,
    UNIQUE KEY correo (correo)
);

-- Table for publication categories
CREATE TABLE IF NOT EXISTS categories (
    id   INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE
);

-- Table for publications metadata (CIDs are the links to P2P content)
CREATE TABLE IF NOT EXISTS publications (
    cid_content  VARCHAR(255) PRIMARY KEY,
    id_autor     INT NOT NULL,
    id_categoria INT NOT NULL,
    titulo       VARCHAR(255) NOT NULL,
    fecha        DATETIME NOT NULL,
    INDEX (id_autor),
    INDEX (id_categoria),
    FOREIGN KEY (id_autor)     REFERENCES usuarios(id)   ON DELETE CASCADE,
    FOREIGN KEY (id_categoria) REFERENCES categories(id) ON DELETE CASCADE
);

-- Table for publication tags
CREATE TABLE IF NOT EXISTS publicacion_tags (
    id_publicacion VARCHAR(255) NOT NULL,
    nombre_tag     VARCHAR(255) NOT NULL,
    PRIMARY KEY (id_publicacion, nombre_tag),
    FOREIGN KEY (id_publicacion) REFERENCES publications(cid_content) ON DELETE CASCADE
);

-- Table for comments metadata
CREATE TABLE IF NOT EXISTS comments (
    cid_content        VARCHAR(255) PRIMARY KEY,
    publication_cid    VARCHAR(255) NOT NULL,
    id_autor           INT NOT NULL,
    titulo             VARCHAR(255) NOT NULL,
    created_timestamp  DATETIME NOT NULL,
    INDEX (publication_cid),
    INDEX (id_autor),
    FOREIGN KEY (publication_cid) REFERENCES publications(cid_content) ON DELETE CASCADE,
    FOREIGN KEY (id_autor)        REFERENCES usuarios(id) ON DELETE CASCADE
);

-- Table for comment tags
CREATE TABLE IF NOT EXISTS comentario_tags (
    id_comentario VARCHAR(255) NOT NULL,
    id_tag        INT NOT NULL,
    PRIMARY KEY (id_comentario, id_tag),
    FOREIGN KEY (id_comentario) REFERENCES comments(cid_content) ON DELETE CASCADE
);

-- Table for publication votes (0-5 range)
CREATE TABLE IF NOT EXISTS publication_votes (
    cid_content VARCHAR(255) NOT NULL,
    id_usuario  INT NOT NULL,
    puntos      TINYINT NOT NULL CHECK (puntos BETWEEN 0 AND 5),
    PRIMARY KEY (cid_content, id_usuario),
    FOREIGN KEY (cid_content) REFERENCES publications(cid_content) ON DELETE CASCADE,
    FOREIGN KEY (id_usuario)  REFERENCES usuarios(id) ON DELETE CASCADE
);

-- Table for comment votes (0-5 range)
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

-- ── Moderation fields on usuarios ───────────────────────────
ALTER TABLE usuarios
  ADD COLUMN IF NOT EXISTS status       ENUM('NORMAL','EN_REVISION','SUSPENDIDO','BANEADO') NOT NULL DEFAULT 'NORMAL',
  ADD COLUMN IF NOT EXISTS strikes_count TINYINT UNSIGNED NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS ban_until    DATETIME NULL DEFAULT NULL;

-- Reports of one user by another (max once per pair)
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

-- Active moderation case per user (at most one OPEN at a time)
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

-- One vote per user per moderation case
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

-- Tracks eliminated P2P content (CIDs) so the feed can filter them
CREATE TABLE IF NOT EXISTS content_status (
    cid            VARCHAR(255) PRIMARY KEY,
    tipo           ENUM('publicacion','comentario') NOT NULL,
    status         ENUM('ELIMINADA','ELIMINADO') NOT NULL,
    deleted_reason ENUM('AUTOR_BANEADO','PUBLICACION_PADRE_ELIMINADA','MODERACION_COMUNITARIA') NOT NULL,
    deleted_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);
