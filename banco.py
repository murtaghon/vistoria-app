import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'vistoria.db')

def conectar():
    return sqlite3.connect(DB_PATH)

def inicializar():
    conn = conectar()
    c = conn.cursor()

    # Tabela de usuários
    c.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            senha TEXT NOT NULL,
            criado_em TEXT DEFAULT (datetime('now'))
        )
    ''')

    # Tabela de laudos
    c.execute('''
        CREATE TABLE IF NOT EXISTS laudos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER NOT NULL,
            endereco TEXT,
            laudo_texto TEXT NOT NULL,
            pdf_path TEXT,
            criado_em TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
        )
    ''')

    conn.commit()
    conn.close()
    print("Banco de dados inicializado!")

if __name__ == '__main__':
    inicializar()