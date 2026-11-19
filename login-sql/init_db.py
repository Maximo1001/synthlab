import sqlite3

con = sqlite3.connect("reservas.db")
cur = con.cursor()

cur.execute("DROP TABLE IF EXISTS usuarios")
cur.execute("DROP TABLE IF EXISTS reservas")

cur.execute("""
CREATE TABLE usuarios (
    id INTEGER PRIMARY KEY,
    nombre TEXT,
    clave TEXT,
    hash TEXT
)
""")

cur.execute("""
CREATE TABLE reservas (
    id INTEGER PRIMARY KEY,
    usuario_id INTEGER,
    destino TEXT,
    fecha TEXT,
    precio REAL
)
""")

cur.execute("INSERT INTO usuarios (id, nombre, clave, hash) VALUES (1, 'lucia', 'Lucia.2026', '5f4dcc3b5aa765d61d8327deb882cf99')")
cur.execute("INSERT INTO usuarios (id, nombre, clave, hash) VALUES (2, 'marcos', 'Marcos.2025', '098f6bcd4621d373cade4e832627b4f6')")

cur.execute("INSERT INTO reservas (id, usuario_id, destino, fecha, precio) VALUES (1, 1, 'Valencia', '2026-12-01', 120.0)")
cur.execute("INSERT INTO reservas (id, usuario_id, destino, fecha, precio) VALUES (2, 2, 'Roma', '2026-12-15', 340.0)")

con.commit()
con.close()
print("Base de datos creada: reservas.db")
