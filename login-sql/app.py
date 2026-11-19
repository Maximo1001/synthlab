from flask import Flask, request, redirect, session, send_from_directory
import sqlite3, os

app = Flask(__name__)
app.secret_key = "miweb-dev-secret-cambiame"
CARPETA = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(CARPETA, "reservas.db")

def get_db():
    return sqlite3.connect(DB)

@app.route("/")
def home():
    return send_from_directory(CARPETA, "index.html")

@app.route("/salud")
def salud():
    return "OK"

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return send_from_directory(CARPETA, "index.html")
    nombre = request.form.get("nombre", "")
    clave = request.form.get("clave", "")
    con = get_db(); cur = con.cursor()
    cur.execute("SELECT id, clave FROM usuarios WHERE nombre = ?", (nombre,))
    row = cur.fetchone(); con.close()
    if row and row[1] == clave:
        session["usuario_id"] = row[0]
        return "Bienvenido/a"
    return "Credenciales incorrectas", 401

@app.route("/registro", methods=["GET", "POST"])
def registro():
    return "<h1>Registro</h1>"

@app.route("/reservas")
def reservas_lista():
    if "usuario_id" not in session:
        return redirect("/login")
    return "<h1>Tus reservas</h1>"

@app.route("/reservas/<int:id>")
def reserva_detalle(id):
    con = get_db(); cur = con.cursor()
    cur.execute("SELECT destino, fecha, precio FROM reservas WHERE id = ?", (id,))
    row = cur.fetchone(); con.close()
    if not row:
        return "No encontrada", 404
    destino, fecha, precio = row
    return f"<h1>Reserva #{id}</h1><p>{fecha}</p><table><tr><td>{destino}</td><td>{fecha}</td><td>{precio}</td></tr></table>"

@app.route("/buscar")
def buscar():
    if "usuario_id" not in session:
        return "No autorizado", 401
    q = request.args.get("q", "")
    usuario_id = session["usuario_id"]
    con = get_db(); cur = con.cursor()
    sql = f"SELECT id, destino, fecha, precio FROM reservas WHERE usuario_id = {usuario_id} AND destino LIKE '%{q}%'"
    cur.execute(sql)
    rows = cur.fetchall(); con.close()
    html = "<table>"
    for r in rows:
        html += "<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>"
    html += "</table>"
    return html

@app.route("/admin")
def admin():
    return "Prohibido", 403

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
