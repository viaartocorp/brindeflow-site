import csv
import io
import json
import os
import sqlite3
from datetime import datetime
from functools import wraps

import requests
from dotenv import load_dotenv
from flask import (
    Flask,
    Response,
    flash,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-change-me")

DATABASE = os.environ.get("DATABASE_PATH", "/app/data/registrations.db")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "changeme")


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def get_db():
    if "db" not in g:
        os.makedirs(os.path.dirname(DATABASE), exist_ok=True)
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exception):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    db.execute("""
        CREATE TABLE IF NOT EXISTS registrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            telefone TEXT NOT NULL,
            cnpj TEXT NOT NULL,
            razao_social TEXT,
            nome_fantasia TEXT,
            cep TEXT,
            endereco TEXT,
            numero TEXT,
            complemento TEXT,
            bairro TEXT,
            cidade TEXT,
            uf TEXT,
            site TEXT,
            instagram TEXT,
            num_funcionarios TEXT,
            empresas_brinde TEXT,
            segmento TEXT,
            como_conheceu TEXT,
            termos_aceitos BOOLEAN DEFAULT 0,
            status TEXT DEFAULT 'pendente',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            notes TEXT
        )
    """)
    db.commit()


with app.app_context():
    init_db()


# ---------------------------------------------------------------------------
# Admin auth decorator
# ---------------------------------------------------------------------------

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("admin"):
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return decorated


# ---------------------------------------------------------------------------
# Registration routes
# ---------------------------------------------------------------------------

@app.route("/cadastro")
def cadastro():
    return render_template("cadastro.html")


@app.route("/api/registrations", methods=["POST"])
def create_registration():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Dados inválidos"}), 400

    required = ["nome", "email", "telefone", "cnpj"]
    for field in required:
        if not data.get(field, "").strip():
            return jsonify({"error": f"Campo obrigatório: {field}"}), 400

    empresas = data.get("empresas_brinde", [])
    if isinstance(empresas, list):
        empresas = json.dumps(empresas)

    db = get_db()
    try:
        db.execute(
            """INSERT INTO registrations
               (nome, email, telefone, cnpj, razao_social, nome_fantasia,
                cep, endereco, numero, complemento, bairro, cidade, uf,
                site, instagram, num_funcionarios, empresas_brinde,
                segmento, como_conheceu, termos_aceitos)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                data["nome"].strip(),
                data["email"].strip().lower(),
                data["telefone"].strip(),
                data["cnpj"].strip(),
                data.get("razao_social", "").strip(),
                data.get("nome_fantasia", "").strip(),
                data.get("cep", "").strip(),
                data.get("endereco", "").strip(),
                data.get("numero", "").strip(),
                data.get("complemento", "").strip(),
                data.get("bairro", "").strip(),
                data.get("cidade", "").strip(),
                data.get("uf", "").strip(),
                data.get("site", "").strip(),
                data.get("instagram", "").strip(),
                data.get("num_funcionarios", "").strip(),
                empresas,
                data.get("segmento", "").strip(),
                data.get("como_conheceu", "").strip(),
                1 if data.get("termos_aceitos") else 0,
            ),
        )
        db.commit()
    except sqlite3.IntegrityError:
        return jsonify({"error": "Este e-mail já está cadastrado."}), 409

    return jsonify({"ok": True}), 201


# ---------------------------------------------------------------------------
# CNPJ proxy (avoids CORS issues with cnpj.ws)
# ---------------------------------------------------------------------------

@app.route("/api/cnpj/<cnpj>")
def cnpj_lookup(cnpj):
    cnpj = cnpj.replace(".", "").replace("/", "").replace("-", "")
    if len(cnpj) != 14 or not cnpj.isdigit():
        return jsonify({"error": "CNPJ inválido"}), 400

    try:
        resp = requests.get(
            f"https://publica.cnpj.ws/cnpj/{cnpj}",
            timeout=10,
            headers={"Accept": "application/json"},
        )
        if resp.status_code == 200:
            return jsonify(resp.json())
        return jsonify({"error": "CNPJ não encontrado"}), resp.status_code
    except requests.RequestException:
        return jsonify({"error": "Erro ao consultar CNPJ"}), 502


# ---------------------------------------------------------------------------
# CEP proxy (viacep.com.br)
# ---------------------------------------------------------------------------

@app.route("/api/cep/<cep>")
def cep_lookup(cep):
    cep = cep.replace("-", "").replace(".", "")
    if len(cep) != 8 or not cep.isdigit():
        return jsonify({"error": "CEP inválido"}), 400

    try:
        resp = requests.get(f"https://viacep.com.br/ws/{cep}/json/", timeout=10)
        if resp.status_code == 200:
            return jsonify(resp.json())
        return jsonify({"error": "CEP não encontrado"}), resp.status_code
    except requests.RequestException:
        return jsonify({"error": "Erro ao consultar CEP"}), 502


# ---------------------------------------------------------------------------
# Admin routes
# ---------------------------------------------------------------------------

@app.route("/admin")
def admin_login():
    if session.get("admin"):
        return redirect(url_for("admin_dashboard"))
    return render_template("admin_login.html")


@app.route("/admin/login", methods=["POST"])
def admin_login_post():
    password = request.form.get("password", "")
    if password == ADMIN_PASSWORD:
        session["admin"] = True
        return redirect(url_for("admin_dashboard"))
    flash("Senha incorreta.")
    return redirect(url_for("admin_login"))


@app.route("/admin/logout")
def admin_logout():
    session.pop("admin", None)
    return redirect(url_for("admin_login"))


@app.route("/admin/dashboard")
@admin_required
def admin_dashboard():
    db = get_db()
    registrations = db.execute(
        "SELECT * FROM registrations ORDER BY created_at DESC"
    ).fetchall()
    return render_template("admin_dashboard.html", registrations=registrations)


@app.route("/admin/registrations/<int:reg_id>/status", methods=["POST"])
@admin_required
def update_status(reg_id):
    new_status = request.form.get("status")
    if new_status not in ("pendente", "aprovado", "rejeitado"):
        return jsonify({"error": "Status inválido"}), 400

    db = get_db()
    db.execute(
        "UPDATE registrations SET status = ? WHERE id = ?", (new_status, reg_id)
    )
    db.commit()
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/registrations/<int:reg_id>/notes", methods=["POST"])
@admin_required
def update_notes(reg_id):
    notes = request.form.get("notes", "")
    db = get_db()
    db.execute("UPDATE registrations SET notes = ? WHERE id = ?", (notes, reg_id))
    db.commit()
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/export")
@admin_required
def export_csv():
    db = get_db()
    rows = db.execute(
        "SELECT * FROM registrations ORDER BY created_at DESC"
    ).fetchall()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(rows[0].keys() if rows else [])
    for row in rows:
        writer.writerow(list(row))

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=cadastros_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        },
    )


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
