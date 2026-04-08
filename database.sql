-- FODES Database Schema
-- Based on P2P Node indexing and API requirements

CREATE DATABASE IF NOT EXISTS FODES2;
USE FODES2;

-- Table for user management
CREATE TABLE IF NOT EXISTS usuarios (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(255) NOT NULL,
    correo VARCHAR(255) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL
);

-- Table for publication categories
CREATE TABLE IF NOT EXISTS categories (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE
);

-- Table for publications metadata (CIDs are the links to P2P content)
CREATE TABLE IF NOT EXISTS publications (
    cid_content VARCHAR(255) PRIMARY KEY,
    id_autor INT NOT NULL,
    id_categoria INT NOT NULL,
    titulo VARCHAR(255) NOT NULL,
    fecha DATETIME NOT NULL,
    INDEX (id_autor),
    INDEX (id_categoria),
    FOREIGN KEY (id_autor) REFERENCES usuarios(id) ON DELETE CASCADE,
    FOREIGN KEY (id_categoria) REFERENCES categories(id) ON DELETE CASCADE
);

-- Table for publication tags
CREATE TABLE IF NOT EXISTS publicacion_tags (
    id_publicacion VARCHAR(255) NOT NULL,
    nombre_tag VARCHAR(255) NOT NULL,
    PRIMARY KEY (id_publicacion, nombre_tag),
    FOREIGN KEY (id_publicacion) REFERENCES publications(cid_content) ON DELETE CASCADE
);

-- Table for comments metadata
CREATE TABLE IF NOT EXISTS comments (
    cid_content VARCHAR(255) PRIMARY KEY,
    publication_cid VARCHAR(255) NOT NULL,
    id_autor INT NOT NULL,
    titulo VARCHAR(255) NOT NULL,
    created_timestamp DATETIME NOT NULL,
    INDEX (publication_cid),
    INDEX (id_autor),
    FOREIGN KEY (publication_cid) REFERENCES publications(cid_content) ON DELETE CASCADE,
    FOREIGN KEY (id_autor) REFERENCES usuarios(id) ON DELETE CASCADE
);

-- Table for comment tags
CREATE TABLE IF NOT EXISTS comentario_tags (
    id_comentario VARCHAR(255) NOT NULL,
    id_tag INT NOT NULL,
    PRIMARY KEY (id_comentario, id_tag),
    FOREIGN KEY (id_comentario) REFERENCES comments(cid_content) ON DELETE CASCADE
);

-- Table for publication votes (0-5 range)
CREATE TABLE IF NOT EXISTS publication_votes (
    cid_content VARCHAR(255) NOT NULL,
    id_usuario INT NOT NULL,
    puntos TINYINT NOT NULL CHECK (puntos BETWEEN 0 AND 5),
    PRIMARY KEY (cid_content, id_usuario),
    FOREIGN KEY (cid_content) REFERENCES publications(cid_content) ON DELETE CASCADE,
    FOREIGN KEY (id_usuario) REFERENCES usuarios(id) ON DELETE CASCADE
);

-- Table for comment votes (0-5 range)
CREATE TABLE IF NOT EXISTS comment_votes (
    cid_content VARCHAR(255) NOT NULL,
    id_usuario INT NOT NULL,
    puntos TINYINT NOT NULL CHECK (puntos BETWEEN 0 AND 5),
    PRIMARY KEY (cid_content, id_usuario),
    FOREIGN KEY (cid_content) REFERENCES comments(cid_content) ON DELETE CASCADE,
    FOREIGN KEY (id_usuario) REFERENCES usuarios(id) ON DELETE CASCADE
);

-- Initial data for categories
INSERT IGNORE INTO categories (name) VALUES 
('Tecnología'),
('Ciencia'),
('Arte'),
('Educación'),
('Social');
