from flask import Flask, request, redirect, session
import sqlite3

app = Flask(__name__)
app.secret_key = "miweb-dev-secret-cambiame"

DB = "reservas.db"

def get_db():
    return sqlite3.connect(DB)

@app.route("/")
def home():
    return "<h1>Mi web de viajes</h1><p><a href='/login'>Entrar</a></p>"

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return """
        <form method="post">
          Usuario: <input name="nombre"><br>
          Clave: <input name="clave" type="password"><br>
          <button type="submit">Entrar</button>
        </form>
        """
    nombre = request.form.get("nombre", "")
    clave = request.form.get("clave", "")
    con = get_db()
    cur = con.cursor()
    cur.execute("SELECT id, clave FROM usuarios WHERE nombre = ?", (nombre,))
    row = cur.fetchone()
    con.close()
    if row and row[1] == clave:
        session["usuario_id"] = row[0]
        return "Bienvenido/a"
    return "Credenciales incorrectas", 401

@app.route("/buscar")
def buscar():
    if "usuario_id" not in session:
        return "No autorizado", 401
    q = request.args.get("q", "")
    usuario_id = session["usuario_id"]
    con = get_db()
    cur = con.cursor()
    sql = f"SELECT id, destino, fecha, precio FROM reservas WHERE usuario_id = {usuario_id} AND destino LIKE '%{q}%'"
    cur.execute(sql)
    rows = cur.fetchall()
    con.close()
    html = "<table>"
    for r in rows:
        html += "<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>"
    html += "</table>"
    return html

@app.route("/reservas/<int:id>")
def reserva_detalle(id):
    con = get_db()
    cur = con.cursor()
    cur.execute("SELECT destino, fecha, precio FROM reservas WHERE id = ?", (id,))
    row = cur.fetchone()
    con.close()
    if not row:
        return "No encontrada", 404
    destino, fecha, precio = row
    return f"<h1>Reserva #{id}</h1><p>{fecha}</p><table><tr><td>{destino}</td><td>{fecha}</td><td>{precio}</td></tr></table>"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
