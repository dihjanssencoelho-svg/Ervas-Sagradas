"""
Enciclopédia das Ervas Sagradas — Flask + SQLite
Execute: python app.py
Acesse:  http://localhost:5000
"""
import json
import sqlite3
import os
import secrets
import re
from pathlib import Path
from functools import wraps
from urllib.parse import urlparse
from flask import (
    Flask, render_template, request, redirect, url_for,
    jsonify, flash, g, session, abort
)
from werkzeug.security import check_password_hash, generate_password_hash

# ── Configuração ──────────────────────────────────────────────────────────────

BASE_DIR   = Path(__file__).parent
DB_PATH    = Path(os.environ.get("DATABASE_PATH", str(BASE_DIR / "ervas.db"))).expanduser()
SECRET_KEY = os.environ.get("SECRET_KEY")
APP_ENV = os.environ.get("APP_ENV", "development").lower()
LOCAL_ADMIN_CONFIG = BASE_DIR / "instance" / "admin_credentials.json"
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "")
ADMIN_PASSWORD_HASH = os.environ.get("ADMIN_PASSWORD_HASH", "")
if APP_ENV != "production" and (not ADMIN_USERNAME or not ADMIN_PASSWORD_HASH):
    try:
        local_admin = json.loads(LOCAL_ADMIN_CONFIG.read_text(encoding="utf-8"))
        ADMIN_USERNAME = ADMIN_USERNAME or local_admin.get("username", "")
        ADMIN_PASSWORD_HASH = ADMIN_PASSWORD_HASH or local_admin.get("password_hash", "")
    except (OSError, json.JSONDecodeError, AttributeError):
        pass

if APP_ENV == "production" and not SECRET_KEY:
    raise RuntimeError("Configure SECRET_KEY antes de iniciar em produção.")
if APP_ENV == "production" and (not ADMIN_USERNAME or not ADMIN_PASSWORD_HASH):
    raise RuntimeError("Configure ADMIN_USERNAME e ADMIN_PASSWORD_HASH antes de iniciar em produção.")

app = Flask(__name__)
app.secret_key = SECRET_KEY or secrets.token_hex(32)
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=APP_ENV == "production",
    MAX_CONTENT_LENGTH=64 * 1024,
)

def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not ADMIN_USERNAME or not ADMIN_PASSWORD_HASH:
            abort(503, description="Painel administrativo não configurado.")
        if not session.get("admin_authenticated"):
            return redirect(url_for("admin_login", next=request.path))
        return view(*args, **kwargs)
    return wrapped

def csrf_token():
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
    return token

@app.context_processor
def inject_template_security():
    return {
        "csrf_token": csrf_token,
        "admin_authenticated": bool(session.get("admin_authenticated")),
        "catalog_authenticated": bool(session.get("admin_authenticated") or session.get("catalog_user_id")),
        "catalog_username": session.get("catalog_username", ""),
    }

@app.before_request
def validate_admin_csrf():
    if request.method == "POST" and (request.path.startswith("/admin/") or request.path in {"/login", "/logout"}):
        supplied = request.form.get("csrf_token", "")
        expected = session.get("csrf_token", "")
        if not supplied or not secrets.compare_digest(supplied, expected):
            abort(400, description="Token de segurança inválido. Recarregue a página e tente novamente.")

@app.before_request
def require_catalog_login():
    if request.endpoint in {"static", "login", "logout", "admin_login"} or request.path.startswith("/admin"):
        return None
    if session.get("admin_authenticated"):
        return None
    user_id = session.get("catalog_user_id")
    if user_id:
        user = get_db().execute(
            "SELECT username FROM catalog_users WHERE id=? AND active=1", (user_id,)
        ).fetchone()
        if user:
            session["catalog_username"] = user["username"]
            return None
        session.clear()
    if request.path.startswith("/api/"):
        return jsonify({"error": "Entre para acessar o catálogo."}), 401
    return redirect(url_for("login", next=request.path))

# ── Banco de Dados ────────────────────────────────────────────────────────────

def get_db():
    if "db" not in g:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        g.db = sqlite3.connect(DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES, timeout=30)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
        g.db.execute("PRAGMA journal_mode = WAL")
    return g.db

@app.teardown_appcontext
def close_db(exc=None):
    db = g.pop("db", None)
    if db:
        db.close()

SUPPLEMENTAL_ITEMS = [
    {
        "name": "Cúrcuma-da-Terra", "sci": "Curcuma longa L.", "emoji": "🫚", "cat": "raiz",
        "desc": "Rizoma aromático usado como especiaria e corante em diferentes cozinhas. Ficha de identificação botânica e cultural; não apresenta indicação medicinal.",
        "img_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5b/Curcuma_longa_roots.jpg/640px-Curcuma_longa_roots.jpg",
        "medical_sources": "Identidade taxonômica: Kew Plants of the World Online — https://powo.science.kew.org/taxon/urn:lsid:ipni.org:names:796451-1. Não há alegação medicinal nesta ficha.",
    },
    {
        "name": "Casca de Laranja", "sci": "Citrus × aurantium f. aurantium", "emoji": "🍊", "cat": "casca",
        "desc": "Registro da casca cítrica como parte vegetal distinta da flor, folha e fruto. A identificação deve acompanhar a espécie e o produto de origem.",
        "img_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/42/Citrus_sinensis.jpg/640px-Citrus_sinensis.jpg",
        "medical_sources": "Taxonomia do grupo da laranja-doce e sinonímia: Kew Plants of the World Online — https://powo.science.kew.org/taxon/772052-1. Sem indicação medicinal individual.",
    },
    {
        "name": "Casca de Limão", "sci": "Citrus × limon (L.) Osbeck", "emoji": "🍋", "cat": "casca",
        "desc": "Registro da casca do limão como parte vegetal. O nome popular pode abranger cultivares e produtos diferentes; esta ficha não recomenda ingestão ou aplicação.",
        "img_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/b/b7/Lemon_closeup.jpg/640px-Lemon_closeup.jpg",
        "medical_sources": "Identidade taxonômica: Kew Plants of the World Online — https://powo.science.kew.org/taxon/60454758-2. Sem indicação medicinal individual.",
    },
    {
        "name": "Água de Rosas", "sci": "Rosa × damascena Herrm. (produto floral)", "emoji": "🌹", "cat": "liquido",
        "desc": "Produto floral associado à destilação de pétalas de rosa. Formulação, conservação e composição variam entre fabricantes; cadastro informativo, sem indicação de ingestão ou aplicação.",
        "img_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/ad/Rosa_damascena_kelaa_mgouna_Morocco.jpg/500px-Rosa_damascena_kelaa_mgouna_Morocco.jpg",
        "medical_sources": "Nome taxonômico: Kew Medicinal Plant Names Services — https://mpns.science.kew.org/mpns-portal/plantDetail?dbs=wcsCmp&filter=latinKewPrefName%3A%22Rosa+%C3%97+damascena+Herrm.%22&fuzzy=false&nameType=all&plantId=2968261. Produto floral não equivale a medicamento.",
    },
    {
        "name": "Água de Flor de Laranjeira", "sci": "Citrus aurantium L. (produto floral)", "emoji": "🍊", "cat": "liquido",
        "desc": "Água floral comercial associada à flor de laranjeira-amarga. A composição depende do rótulo e do processo do fabricante; esta ficha não recomenda ingestão, inalação ou uso na pele.",
        "img_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/f/fb/Citrus-aurantium-20080320-3.JPG/640px-Citrus-aurantium-20080320-3.JPG",
        "medical_sources": "Identificação de Citrus sinensis dentro da classificação de Citrus: Kew Plants of the World Online — https://powo.science.kew.org/taxon/772052-1. Produto floral não equivale a medicamento.",
    },
    {
        "name": "Hidrolato de Lavanda", "sci": "Lavandula angustifolia Mill. (produto floral)", "emoji": "💧", "cat": "liquido",
        "desc": "Água floral comercial associada à destilação de lavanda. Produtos podem ter composição e conservação diferentes; cadastro de identificação, sem indicação de ingestão ou aplicação.",
        "img_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/7/7b/Lavande_en_fleurs.jpg/640px-Lavande_en_fleurs.jpg",
        "medical_sources": "Identidade taxonômica: Kew Plants of the World Online — https://powo.science.kew.org/taxon/449008-1. Produto floral não equivale a medicamento.",
    },
]

def _migrate_liquido_category(db):
    table = db.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='ervas'").fetchone()
    if not table or "'liquido'" in table[0]:
        return
    db.execute("PRAGMA foreign_keys=OFF")
    db.execute("BEGIN IMMEDIATE")
    try:
        db.execute("DROP TABLE IF EXISTS ervas_new")
        db.execute("""
            CREATE TABLE ervas_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                sci TEXT,
                emoji TEXT DEFAULT '🌿',
                temp TEXT CHECK(temp IN ('quente','fria','morna','neutra')),
                elem TEXT CHECK(elem IN ('fogo','água','terra','ar')),
                cat TEXT CHECK(cat IN ('erva','folha','flor','raiz','casca','resina','semente','fruto','liquido')),
                desc TEXT,
                spiritual TEXT,
                bath_uses TEXT DEFAULT '[]',
                tea_uses TEXT DEFAULT '[]',
                can_fumigate INTEGER DEFAULT 0,
                fumig TEXT,
                orixas TEXT DEFAULT '[]',
                colors TEXT DEFAULT '[]',
                compat TEXT DEFAULT '[]',
                incompat TEXT DEFAULT '[]',
                preparo TEXT,
                img_url TEXT,
                recommended TEXT DEFAULT '[]',
                contraindications TEXT DEFAULT 'Não avaliadas individualmente; não presumir segurança para ingestão ou uso tópico.',
                medical_sources TEXT DEFAULT 'Sem referência específica revisada para esta espécie.',
                is_custom INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        columns = [row[1] for row in db.execute("PRAGMA table_info(ervas)")]
        column_sql = ", ".join('"' + column.replace('"', '""') + '"' for column in columns)
        db.execute(f"INSERT INTO ervas_new ({column_sql}) SELECT {column_sql} FROM ervas")
        db.execute("DROP TABLE ervas")
        db.execute("ALTER TABLE ervas_new RENAME TO ervas")
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.execute("PRAGMA foreign_keys=ON")

def _seed_supplemental_items(db):
    db.execute("CREATE TABLE IF NOT EXISTS app_migrations (name TEXT PRIMARY KEY, applied_at TEXT DEFAULT (datetime('now')))")
    migration = "catalog_supplemental_2026_10"
    if db.execute("SELECT 1 FROM app_migrations WHERE name=?", (migration,)).fetchone():
        return
    for item in SUPPLEMENTAL_ITEMS:
        if db.execute("SELECT 1 FROM ervas WHERE lower(name)=lower(?)", (item["name"],)).fetchone():
            continue
        db.execute("""
            INSERT INTO ervas
              (name,sci,emoji,temp,elem,cat,desc,spiritual,bath_uses,tea_uses,
               can_fumigate,fumig,orixas,colors,compat,incompat,preparo,img_url,
               recommended,contraindications,medical_sources,is_custom)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,0)
        """, (
            item["name"], item["sci"], item["emoji"], "neutra", "terra", item["cat"],
            item["desc"], "Sem atribuição de tradição religiosa específica nesta ficha.",
            "[]", "[]", 0, "", "[]", "[]", "[]", "[]",
            "Registro de identificação; nenhum modo de uso medicinal recomendado.",
            item["img_url"], "[]",
            "Não avaliado para ingestão, inalação ou aplicação no corpo. Consulte a identificação do produto e orientação profissional.",
            item["medical_sources"],
        ))
    db.execute("INSERT INTO app_migrations(name) VALUES (?)", (migration,))

def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH, timeout=30)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    db.execute("PRAGMA journal_mode = WAL")

    db.executescript("""
    CREATE TABLE IF NOT EXISTS catalog_users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL COLLATE NOCASE UNIQUE,
        password_hash TEXT NOT NULL,
        active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS ervas (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        name        TEXT    NOT NULL,
        sci         TEXT,
        emoji       TEXT    DEFAULT '🌿',
        temp        TEXT    CHECK(temp IN ('quente','fria','morna','neutra')),
        elem        TEXT    CHECK(elem IN ('fogo','água','terra','ar')),
        cat         TEXT    CHECK(cat IN ('erva','folha','flor','raiz','casca','resina','semente','fruto','liquido')),
        desc        TEXT,
        spiritual   TEXT,
        bath_uses   TEXT    DEFAULT '[]',
        tea_uses    TEXT    DEFAULT '[]',
        can_fumigate INTEGER DEFAULT 0,
        fumig       TEXT,
        orixas      TEXT    DEFAULT '[]',
        colors      TEXT    DEFAULT '[]',
        compat      TEXT    DEFAULT '[]',
        incompat    TEXT    DEFAULT '[]',
        preparo     TEXT,
        img_url     TEXT,
        recommended TEXT    DEFAULT '[]',
        contraindications TEXT DEFAULT 'Não avaliadas individualmente; não presumir segurança para ingestão ou uso tópico.',
        medical_sources TEXT DEFAULT 'Sem referência específica revisada para esta espécie.',
        is_custom   INTEGER DEFAULT 0,
        created_at  TEXT    DEFAULT (datetime('now'))
    );
    """)
    existing = {row[1] for row in db.execute("PRAGMA table_info(ervas)")}
    if "contraindications" not in existing:
        db.execute("ALTER TABLE ervas ADD COLUMN contraindications TEXT DEFAULT 'Não avaliadas individualmente; não presumir segurança para ingestão ou uso tópico.'")
    if "medical_sources" not in existing:
        db.execute("ALTER TABLE ervas ADD COLUMN medical_sources TEXT DEFAULT 'Sem referência específica revisada para esta espécie.'")
    db.commit()
    _migrate_liquido_category(db)
    db.commit()

    # Seed inicial se a tabela estiver vazia
    count = db.execute("SELECT COUNT(*) FROM ervas").fetchone()[0]
    if count == 0:
        _seed_herbs(db)
    _seed_supplemental_items(db)
    db.commit()

    db.close()

def _seed_herbs(db):
    """Insere os registros iniciais do catálogo."""
    herbs = _get_seed_data()
    for h in herbs:
        db.execute("""
            INSERT INTO ervas
              (name,sci,emoji,temp,elem,cat,desc,spiritual,
               bath_uses,tea_uses,can_fumigate,fumig,orixas,colors,
               compat,incompat,preparo,img_url,recommended,is_custom)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,0)
        """, (
            h["name"], h.get("sci",""), h.get("emoji","🌿"),
            h.get("temp","neutra"), h.get("elem","ar"), h.get("cat","erva"),
            h.get("desc",""), h.get("spiritual",""),
            json.dumps(h.get("bath_uses",[]), ensure_ascii=False),
            json.dumps(h.get("tea_uses",[]),  ensure_ascii=False),
            1 if h.get("can_fumigate") else 0,
            h.get("fumig",""),
            json.dumps(h.get("orixas",[]),  ensure_ascii=False),
            json.dumps(h.get("colors",[]),  ensure_ascii=False),
            json.dumps(h.get("compat",[]),  ensure_ascii=False),
            json.dumps(h.get("incompat",[]),ensure_ascii=False),
            h.get("preparo",""),
            h.get("img_url",""),
            json.dumps(h.get("recommended",[]), ensure_ascii=False),
        ))
    db.commit()

# ── Helpers ───────────────────────────────────────────────────────────────────

def row_to_dict(row):
    d = dict(row)
    for field in ("bath_uses","tea_uses","orixas","colors","compat","incompat","recommended"):
        try:
            d[field] = json.loads(d.get(field) or "[]")
        except (json.JSONDecodeError, TypeError):
            d[field] = []
    d["can_fumigate"] = bool(d.get("can_fumigate", 0))
    d["is_custom"]    = bool(d.get("is_custom", 0))
    d["contraindications"] = d.get("contraindications") or "Não avaliadas individualmente; não presumir segurança para ingestão ou uso tópico."
    d["medical_sources"] = d.get("medical_sources") or "Sem referência específica revisada para esta espécie."
    return d

def public_herb_dict(row):
    """Preserva os textos descritivos e tradicionais conforme cadastrados."""
    return row_to_dict(row)

def get_stats(db):
    rows = db.execute("""
        SELECT
          COUNT(*)                                          AS total,
          SUM(CASE WHEN can_fumigate = 1 THEN 1 ELSE 0 END) AS defumacao,
          SUM(CASE WHEN json_array_length(bath_uses) > 0 THEN 1 ELSE 0 END) AS banho,
          SUM(CASE WHEN json_array_length(tea_uses)  > 0 THEN 1 ELSE 0 END) AS cha
        FROM ervas
    """).fetchone()
    return dict(rows) if rows else {"total":0,"defumacao":0,"banho":0,"cha":0}

# ── Rotas principais ──────────────────────────────────────────────────────────

@app.route("/")
def index():
    db    = get_db()
    stats = get_stats(db)
    return render_template("index.html", stats=stats)

@app.route("/api/ervas")
def api_ervas():
    """Retorna lista filtrada de ervas como JSON."""
    db   = get_db()
    tab  = request.args.get("tab", "ervas")
    q    = request.args.get("q", "").strip().lower()
    temp = request.args.get("temp", "")
    elem = request.args.get("elem", "")
    cat  = request.args.get("cat",  "")

    sql    = "SELECT * FROM ervas WHERE 1=1"
    params = []

    if temp:
        sql += " AND temp = ?"
        params.append(temp)
    if elem:
        sql += " AND elem = ?"
        params.append(elem)
    if cat:
        sql += " AND cat = ?"
        params.append(cat)
    if q:
        sql += """ AND (
            lower(name) LIKE ? OR lower(sci) LIKE ? OR lower(desc) LIKE ? OR
            lower(spiritual) LIKE ? OR lower(bath_uses) LIKE ? OR
            lower(tea_uses) LIKE ? OR lower(orixas) LIKE ?
        )"""
        like = f"%{q}%"
        params.extend([like] * 7)

    sql += " ORDER BY name"
    rows = db.execute(sql, params).fetchall()
    return jsonify([public_herb_dict(r) for r in rows])

@app.route("/api/ervas/<int:herb_id>")
def api_erva_detalhe(herb_id):
    db  = get_db()
    row = db.execute("SELECT * FROM ervas WHERE id = ?", (herb_id,)).fetchone()
    if not row:
        return jsonify({"error": "Não encontrado"}), 404
    return jsonify(public_herb_dict(row))

@app.route("/api/comparar", methods=["POST"])
def api_comparar():
    """Retorna análise de compatibilidade entre 2-3 ervas."""
    if not request.is_json:
        return jsonify({"error": "Envie o conteúdo como application/json."}), 415
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not isinstance(data.get("ids"), list):
        return jsonify({"error": "O campo 'ids' deve ser uma lista JSON."}), 400
    raw_ids = data["ids"]
    if not 2 <= len(raw_ids) <= 3:
        return jsonify({"error": "Informe de 2 a 3 IDs para comparar."}), 400
    if any(type(value) is not int or value <= 0 for value in raw_ids):
        return jsonify({"error": "Todos os IDs devem ser inteiros positivos."}), 400
    ids = raw_ids
    if len(set(ids)) != len(ids):
        return jsonify({"error": "Não repita IDs na comparação."}), 400

    db   = get_db()
    rows = db.execute(
        f"SELECT * FROM ervas WHERE id IN ({','.join('?'*len(ids))})", ids
    ).fetchall()
    herbs = [public_herb_dict(r) for r in rows]
    if len(herbs) != len(ids):
        return jsonify({"error": "Uma ou mais ervas não foram encontradas."}), 404

    pairs = []
    for i, a in enumerate(herbs):
        for b in herbs[i+1:]:
            pairs.append({"a": a["name"], "b": b["name"],
                          "reason": _compat_reason(a, b)})
    return jsonify({"herbs": herbs, "pairs": pairs})

@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("admin_authenticated") or session.get("catalog_user_id"):
        return redirect(url_for("index"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if (
            ADMIN_USERNAME
            and ADMIN_PASSWORD_HASH
            and secrets.compare_digest(username, ADMIN_USERNAME)
            and check_password_hash(ADMIN_PASSWORD_HASH, password)
        ):
            session.clear()
            session["admin_authenticated"] = True
            session["csrf_token"] = secrets.token_urlsafe(32)
            destination = request.args.get("next", "")
            if not destination.startswith("/") or destination.startswith("//"):
                destination = url_for("index")
            return redirect(destination)
        user = get_db().execute(
            "SELECT id, username, password_hash FROM catalog_users WHERE username=? COLLATE NOCASE AND active=1",
            (username,),
        ).fetchone()
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["catalog_user_id"] = user["id"]
            session["catalog_username"] = user["username"]
            session["csrf_token"] = secrets.token_urlsafe(32)
            destination = request.args.get("next", "")
            if not destination.startswith("/") or destination.startswith("//") or destination.startswith("/admin"):
                destination = url_for("index")
            return redirect(destination)
        flash("Login ou senha inválidos ou conta desativada.", "error")
    return render_template("login.html")

@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("Sessão encerrada.", "info")
    return redirect(url_for("login"))

def parse_herb_form(form):
    allowed = {
        "temp": {"quente", "fria", "morna", "neutra"},
        "elem": {"fogo", "água", "terra", "ar"},
        "cat": {"erva", "folha", "flor", "raiz", "casca", "resina", "semente", "fruto", "liquido"},
    }
    limits = {"name": 120, "sci": 160, "emoji": 16, "desc": 2000,
              "spiritual": 2000, "fumig": 1000, "preparo": 1000,
              "img_url": 500, "contraindications": 2000, "medical_sources": 2000}
    values = {key: form.get(key, "").strip() for key in limits}
    if not values["name"]:
        raise ValueError("O nome é obrigatório.")
    for key, maximum in limits.items():
        if len(values[key]) > maximum:
            raise ValueError(f"O campo {key} excede o limite de {maximum} caracteres.")
    for key, options in allowed.items():
        value = form.get(key, "")
        if value not in options:
            raise ValueError(f"Valor inválido para {key}.")
        values[key] = value
    image_url = values["img_url"]
    if image_url:
        parsed = urlparse(image_url)
        if parsed.scheme != "https" or not parsed.netloc:
            raise ValueError("A imagem deve usar uma URL HTTPS válida.")

    def as_json_list(key, maximum_items=30):
        items = [item.strip() for item in form.get(key, "").split(",") if item.strip()]
        if len(items) > maximum_items or any(len(item) > 100 for item in items):
            raise ValueError(f"Lista inválida ou longa demais: {key}.")
        return json.dumps(items, ensure_ascii=False)

    recommended = [name for field, name in (("rec_banho", "banho"), ("rec_cha", "cha"), ("rec_defumacao", "defumacao")) if form.get(field)]
    return {
        "name": values["name"], "sci": values["sci"], "emoji": values["emoji"] or "🌿",
        "temp": values["temp"], "elem": values["elem"], "cat": values["cat"],
        "desc": values["desc"], "spiritual": values["spiritual"],
        "bath_uses": as_json_list("bath_uses"), "tea_uses": as_json_list("tea_uses"),
        "can_fumigate": 1 if form.get("can_fumigate") == "true" else 0,
        "fumig": values["fumig"], "orixas": as_json_list("orixas"),
        "compat": as_json_list("compat"), "incompat": as_json_list("incompat"),
        "preparo": values["preparo"], "img_url": image_url,
        "recommended": json.dumps(recommended, ensure_ascii=False),
        "contraindications": values["contraindications"] or "Não avaliadas individualmente; não presumir segurança para ingestão ou uso tópico.",
        "medical_sources": values["medical_sources"] or "Sem referência específica revisada para esta espécie.",
    }

@app.route("/admin/login.", methods=["GET", "POST"])
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if not ADMIN_USERNAME or not ADMIN_PASSWORD_HASH:
        return render_template("admin_login.html", admin_configured=False), 503
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        if secrets.compare_digest(username, ADMIN_USERNAME) and check_password_hash(ADMIN_PASSWORD_HASH, password):
            session.clear()
            session["admin_authenticated"] = True
            session["csrf_token"] = secrets.token_urlsafe(32)
            destination = request.args.get("next", "")
            if not destination.startswith("/admin") or destination.startswith("//"):
                destination = url_for("admin")
            return redirect(destination)
        flash("Usuário ou senha inválidos.", "error")
    return render_template("admin_login.html")

@app.route("/admin/logout", methods=["POST"])
@admin_required
def admin_logout():
    session.clear()
    flash("Sessão encerrada.", "info")
    return redirect(url_for("index"))

@app.route("/admin")
@admin_required
def admin():
    db    = get_db()
    stats = get_stats(db)
    q     = request.args.get("q","").strip().lower()
    cat   = request.args.get("cat","")

    sql    = "SELECT * FROM ervas WHERE 1=1"
    params = []
    if cat:
        sql += " AND cat = ?"
        params.append(cat)
    if q:
        sql += " AND (lower(name) LIKE ? OR lower(sci) LIKE ? OR lower(orixas) LIKE ?)"
        like = f"%{q}%"
        params.extend([like]*3)
    sql += " ORDER BY name"

    rows  = db.execute(sql, params).fetchall()
    items = [row_to_dict(r) for r in rows]
    users = db.execute(
        "SELECT id, username, created_at FROM catalog_users WHERE active=1 ORDER BY username"
    ).fetchall()
    return render_template("admin.html", items=items, stats=stats, q=q, cat=cat, users=users)

@app.route("/admin/usuarios", methods=["POST"])
@admin_required
def admin_create_user():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    confirmation = request.form.get("password_confirm", "")
    if not re.fullmatch(r"[\w.@+-]{3,80}", username, flags=re.UNICODE):
        flash("Use um login de 3 a 80 caracteres (letras, números, ponto, @, +, _ ou -).", "error")
        return redirect(url_for("admin"))
    if not 8 <= len(password) <= 128:
        flash("A senha do usuário deve ter entre 8 e 128 caracteres.", "error")
        return redirect(url_for("admin"))
    if password != confirmation:
        flash("As senhas não conferem.", "error")
        return redirect(url_for("admin"))
    db = get_db()
    try:
        db.execute(
            "INSERT INTO catalog_users (username, password_hash) VALUES (?, ?)",
            (username, generate_password_hash(password)),
        )
        db.commit()
    except sqlite3.IntegrityError:
        flash("Já existe uma conta com esse login.", "error")
        return redirect(url_for("admin"))
    flash(f"Conta de acesso criada para {username}.", "success")
    return redirect(url_for("admin"))

@app.route("/admin/usuarios/<int:user_id>/remover", methods=["POST"])
@admin_required
def admin_remove_user(user_id):
    db = get_db()
    user = db.execute("SELECT username FROM catalog_users WHERE id=?", (user_id,)).fetchone()
    if user:
        db.execute("DELETE FROM catalog_users WHERE id=?", (user_id,))
        db.commit()
        flash(f"Conta de acesso de {user['username']} removida.", "info")
    return redirect(url_for("admin"))

@app.route("/admin/nova", methods=["GET","POST"])
@admin_required
def admin_nova():
    if request.method == "POST":
        try:
            h = parse_herb_form(request.form)
        except ValueError as exc:
            abort(400, description=str(exc))

        db = get_db()
        db.execute("""
            INSERT INTO ervas
              (name,sci,emoji,temp,elem,cat,desc,spiritual,
               bath_uses,tea_uses,can_fumigate,fumig,orixas,
               compat,incompat,preparo,img_url,recommended,contraindications,medical_sources,is_custom)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1)
        """, (
            *h.values(),
        ))
        db.commit()
        flash(f"Item \"{h['name']}\" salvo com sucesso!", "success")
        return redirect(url_for("admin"))

    return render_template("admin_form.html", herb=None)

@app.route("/admin/editar/<int:herb_id>", methods=["GET","POST"])
@admin_required
def admin_editar(herb_id):
    db  = get_db()
    row = db.execute("SELECT * FROM ervas WHERE id = ?", (herb_id,)).fetchone()
    if not row:
        flash("Item não encontrado.", "error")
        return redirect(url_for("admin"))
    herb = row_to_dict(row)

    if request.method == "POST":
        try:
            h = parse_herb_form(request.form)
        except ValueError as exc:
            abort(400, description=str(exc))

        db.execute("""
            UPDATE ervas SET
              name=?,sci=?,emoji=?,temp=?,elem=?,cat=?,desc=?,spiritual=?,
              bath_uses=?,tea_uses=?,can_fumigate=?,fumig=?,orixas=?,
              compat=?,incompat=?,preparo=?,img_url=?,recommended=?,contraindications=?,medical_sources=?
            WHERE id=?
        """, (
            *h.values(),
            herb_id,
        ))
        db.commit()
        flash(f"Item \"{h['name']}\" atualizado!", "success")
        return redirect(url_for("admin"))

    return render_template("admin_form.html", herb=herb)

@app.route("/admin/remover/<int:herb_id>", methods=["POST"])
@admin_required
def admin_remover(herb_id):
    db  = get_db()
    row = db.execute("SELECT name FROM ervas WHERE id = ?", (herb_id,)).fetchone()
    if row:
        db.execute("DELETE FROM ervas WHERE id = ?", (herb_id,))
        db.commit()
        flash(f"Item \"{row['name']}\" removido.", "info")
    return redirect(url_for("admin"))

# ── Lógica de compatibilidade ─────────────────────────────────────────────────

def _compat_reason(a, b):
    shared_orixas = [o for o in a.get("orixas",[]) if o in b.get("orixas",[])]
    shared_uses   = [t for t in ("banho","cha","defumacao")
                     if t in a.get("recommended",[]) and t in b.get("recommended",[])]

    if b["name"] in a.get("compat",[]) and a["name"] in b.get("compat",[]):
        ostr = ", ".join(shared_orixas) if shared_orixas else "sem orixá em comum"
        return (f"Compatibilidade cultural registrada: ambos se citam mutuamente. "
                f"Compartilham referências a orixás {ostr}. Isso não avalia segurança de uso ou combinação.")
    if b["name"] in a.get("compat",[]) or a["name"] in b.get("compat",[]):
        return ("Compatibilidade cultural parcial registrada: um item cita o outro. "
                "Isso não avalia segurança de uso ou combinação.")
    if b["name"] in a.get("incompat",[]) or a["name"] in b.get("incompat",[]):
        return ("O catálogo registra uma incompatibilidade cultural entre estes itens. "
                "Isso não substitui avaliação de segurança.")
    if shared_orixas:
        return (f"Compartilham referências espirituais a {', '.join(shared_orixas)}. "
                "A semelhança não indica segurança de uso conjunto.")
    if shared_uses:
        return (f"O catálogo registra os mesmos usos tradicionais para {' e '.join(shared_uses)}. "
                "Isso não indica segurança de uso conjunto.")
    return "O catálogo não registra afinidade cultural ou conflito. Segurança de uso não avaliada."

# ── Dados seed ────────────────────────────────────────────────────────────────

def _get_seed_data():
    return [
  # ════════════════════════════════════════════════════════════
  # GRUPO 1 – Proteção e descarrego
  # ════════════════════════════════════════════════════════════
  {"name":"Arruda","sci":"Ruta graveolens","emoji":"🌿","temp":"quente","elem":"fogo","cat":"erva",
   "desc":"Erva de proteção poderosa, usada para limpar energias negativas, afastar inveja e quebrar feitiços.",
   "spiritual":"Proteção, quebra de feitiço e limpeza energética profunda. Uma das ervas mais respeitadas na Umbanda.",
   "bath_uses":["Proteção","Limpeza espiritual","Quebra de feitiço","Descarrego"],"tea_uses":[],
   "can_fumigate":True,"fumig":"Defumação poderosa para cortar energias pesadas e romper demandas.",
   "orixas":["Ogum","Exu"],"compat":["Alecrim","Guiné","Espada-de-São-Jorge","Aroeira"],
   "incompat":["Rosa Branca","Lavanda"],"preparo":"Fresca ou seca. Contraindicada em gestantes.",
   "recommended":["banho","defumacao"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/e/e5/Ruta_graveolens_-_K%C3%B6hler%E2%80%93s_Medizinal-Pflanzen-122.jpg/640px-Ruta_graveolens_-_K%C3%B6hler%E2%80%93s_Medizinal-Pflanzen-122.jpg"},

  {"name":"Guiné","sci":"Petiveria alliacea","emoji":"🌾","temp":"quente","elem":"fogo","cat":"erva",
   "desc":"Erva intensa de limpeza e descarrego espiritual profundo. Usada em sacudimentos e antes de rituais.",
   "spiritual":"Descarrego profundo, afastamento de obsessores e proteção contra espíritos perturbadores.",
   "bath_uses":["Descarrego","Limpeza profunda","Proteção","Afastar obsessão"],"tea_uses":[],
   "can_fumigate":True,"fumig":"Defumação forte de descarrego antes de trabalhos espirituais.",
   "orixas":["Exu","Ogum","Oxóssi"],"compat":["Arruda","Espada-de-São-Jorge","Aroeira"],
   "incompat":["Rosa Branca","Jasmim"],"preparo":"Uso moderado. Contraindicado em gestantes e crianças.",
   "recommended":["banho","defumacao"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/4/4d/Petiveria_alliacea.jpg/640px-Petiveria_alliacea.jpg"},

  {"name":"Espada-de-São-Jorge","sci":"Sansevieria trifasciata","emoji":"🗡️","temp":"quente","elem":"fogo","cat":"folha",
   "desc":"Planta de barreira que corta energias negativas e protege o lar contra inveja e feitiços.",
   "spiritual":"Corte do mal, proteção firme do lar e afastamento de inimigos invisíveis.",
   "bath_uses":["Proteção","Afastar inimigos","Cortar demandas"],"tea_uses":[],
   "can_fumigate":False,"fumig":"","orixas":["Ogum"],
   "compat":["Arruda","Guiné","Alecrim","Aroeira"],"incompat":[],
   "preparo":"Folhas em banhos. Mantê-la viva em casa já protege o ambiente.",
   "recommended":["banho"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/4/4b/Sansevieria_trifasciata_Laurentii.jpg/640px-Sansevieria_trifasciata_Laurentii.jpg"},

  {"name":"Aroeira","sci":"Schinus terebinthifolia","emoji":"🌳","temp":"quente","elem":"fogo","cat":"casca",
   "desc":"Árvore sagrada de descarrego e proteção forte. Uma das ervas mais poderosas da Umbanda.",
   "spiritual":"Corta demandas, rompe feitiços e fortalece o campo áurico contra ataques.",
   "bath_uses":["Descarrego","Quebra de feitiço","Proteção forte"],"tea_uses":[],
   "can_fumigate":True,"fumig":"Defumação de proteção intensa e corte de energias densas.",
   "orixas":["Xangô","Ogum"],"compat":["Arruda","Guiné","Alecrim","Espada-de-São-Jorge"],
   "incompat":["Jasmim","Camomila"],"preparo":"Cascas e folhas em banho quente, do pescoço para baixo.",
   "recommended":["banho","defumacao"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/7/7d/Schinus_terebinthifolia.jpg/640px-Schinus_terebinthifolia.jpg"},

  {"name":"Comigo-Ninguém-Pode","sci":"Dieffenbachia seguine","emoji":"🌿","temp":"quente","elem":"fogo","cat":"folha",
   "desc":"Planta de proteção que afasta inimigos e cria barreiras energéticas ao redor da casa.",
   "spiritual":"Proteção contra feitiçaria, inveja e ataques espirituais diretos.",
   "bath_uses":["Proteção","Afastar inimigos","Quebra de feitiço"],"tea_uses":[],
   "can_fumigate":False,"fumig":"","orixas":["Exu","Ogum"],
   "compat":["Arruda","Espada-de-São-Jorge","Guiné"],"incompat":["Rosa Branca","Camomila"],
   "preparo":"Use com luvas — seiva tóxica. Manter viva no ambiente já protege.",
   "recommended":["banho"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/c/c9/Dieffenbachia_seguine.jpg/640px-Dieffenbachia_seguine.jpg"},

  {"name":"Vassourinha","sci":"Scoparia dulcis","emoji":"🌿","temp":"neutra","elem":"ar","cat":"erva",
   "desc":"Erva de limpeza que varre baixas vibrações e restaura a harmonia do ambiente.",
   "spiritual":"Renovação energética, varredura de pensamentos negativos e limpeza de campos sutis.",
   "bath_uses":["Limpeza","Renovação","Sacudimento"],"tea_uses":["Frescor","Purificação"],
   "can_fumigate":True,"fumig":"Defumação suave para renovar a casa após conflitos.",
   "orixas":["Oxalá","Iemanjá"],"compat":["Alecrim","Alfazema","Camomila"],
   "incompat":[],"preparo":"Sem contraindicações conhecidas. Ideal para sacudimentos.",
   "recommended":["banho","cha","defumacao"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/b/b4/Scoparia_dulcis_%28Habitus%29.jpg/640px-Scoparia_dulcis_%28Habitus%29.jpg"},

  {"name":"Losna","sci":"Artemisia absinthium","emoji":"🌿","temp":"quente","elem":"fogo","cat":"erva",
   "desc":"Erva amarga e forte para afastar maus espíritos e limpar profundamente o ambiente.",
   "spiritual":"Encaminha espíritos desequilibrados e rompe ligações com energias negativas.",
   "bath_uses":["Afastar maus espíritos","Sacudimento ambiental"],"tea_uses":[],
   "can_fumigate":True,"fumig":"Defumação para encaminhar eguns em espaços perturbados.",
   "orixas":["Ogum","Exu"],"compat":["Alecrim","Arruda"],
   "incompat":["Camomila","Jasmim"],"preparo":"Contraindicada em gestantes. Seca em sacudimentos.",
   "recommended":["defumacao"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/0/09/Artemisia_absinthium_2.jpg/640px-Artemisia_absinthium_2.jpg"},

  {"name":"Mamona","sci":"Ricinus communis","emoji":"🌱","temp":"quente","elem":"fogo","cat":"folha",
   "desc":"Planta sagrada de Omolu e Exu, usada em sacudimentos e descarrego de energias densas.",
   "spiritual":"Afasta espíritos perturbadores, remove larvas astrais e protege o lar.",
   "bath_uses":["Descarrego","Afastar obsessores"],"tea_uses":[],
   "can_fumigate":True,"fumig":"Defumação de descarrego com ação rápida.",
   "orixas":["Omolu","Exu","Ogum"],"compat":["Arruda","Guiné","Losna"],
   "incompat":[],"preparo":"Planta tóxica internamente — apenas uso externo.",
   "recommended":["banho","defumacao"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/3/3c/Ricinus_communis_flowers.jpg/640px-Ricinus_communis_flowers.jpg"},

  {"name":"Pinhão Roxo","sci":"Jatropha gossypifolia","emoji":"🌿","temp":"quente","elem":"fogo","cat":"folha",
   "desc":"Planta de afastamento de espíritos desequilibrados, usada em sacudimentos domiciliares.",
   "spiritual":"Afasta eguns e espíritos perturbadores. Usada com cuidado especial nos terreiros.",
   "bath_uses":["Afastar eguns","Sacudimento","Limpeza pesada"],"tea_uses":[],
   "can_fumigate":True,"fumig":"Defumação de descarrego ambiental forte.",
   "orixas":["Exu","Omolu"],"compat":["Arruda","Guiné"],
   "incompat":["Flores suaves"],"preparo":"Planta tóxica — use somente galhos em sacudimentos. Nunca ingira.",
   "recommended":["defumacao"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/1/12/Jatropha_gossypifolia.jpg/640px-Jatropha_gossypifolia.jpg"},

  {"name":"Cipó-Mil-Homens","sci":"Aristolochia cymbifera","emoji":"🌿","temp":"quente","elem":"fogo","cat":"raiz",
   "desc":"Raiz poderosa para afastar obsessão, alcoolismo e desequilíbrios espirituais graves.",
   "spiritual":"Afasta obsessores, corta ligações de desequilíbrio e fortalece a vontade.",
   "bath_uses":["Afastar obsessão","Força de vontade","Descarrego profundo"],"tea_uses":[],
   "can_fumigate":True,"fumig":"Defumação para descarrego de obsessores.",
   "orixas":["Exu","Ogum"],"compat":["Arruda","Guiné","Alecrim"],
   "incompat":[],"preparo":"Contraindicada em gestantes — tóxica. Raiz em banho ou defumação.",
   "recommended":["banho","defumacao"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/8/8a/Aristolochia_cymbifera.jpg/640px-Aristolochia_cymbifera.jpg"},

  # ════════════════════════════════════════════════════════════
  # GRUPO 2 – Amor e atração
  # ════════════════════════════════════════════════════════════
  {"name":"Rosa Vermelha","sci":"Rosa × hybrida","emoji":"🌹","temp":"quente","elem":"fogo","cat":"flor",
   "desc":"Flor de amor, paixão e força espiritual. Símbolo de Oxum, usada para atrair amor.",
   "spiritual":"Atração, fortalecimento de relacionamentos e energia afetiva intensa.",
   "bath_uses":["Amor","Atração","Paixão","Fortalecimento do casal"],"tea_uses":[],
   "can_fumigate":False,"fumig":"","orixas":["Oxum","Iansã"],
   "compat":["Canela","Manjericão","Jasmim","Rosa Amarela"],"incompat":["Arruda","Guiné"],
   "preparo":"Pétalas frescas em banhos de amor. Colher na fase crescente.",
   "recommended":["banho"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/4/41/Simple_botanic_photography.jpg/640px-Simple_botanic_photography.jpg"},

  {"name":"Manjericão","sci":"Ocimum basilicum","emoji":"🌿","temp":"quente","elem":"fogo","cat":"erva",
   "desc":"Erva de prosperidade, harmonia no lar e abertura de caminhos. Pode-se manter viva na entrada.",
   "spiritual":"Atração, proteção do lar e sorte em questões do coração e dos negócios.",
   "bath_uses":["Amor","Prosperidade","Harmonia","Atração"],"tea_uses":["Calma","Clareza","Digestão"],
   "can_fumigate":True,"fumig":"Defumação que atrai prosperidade, amor e boa fortuna.",
   "orixas":["Oxum","Iemanjá","Xangô"],"compat":["Rosa Vermelha","Canela","Alecrim","Colônia"],
   "incompat":[],"preparo":"Melhor fresco. Manter vivo na entrada da casa para proteção.",
   "recommended":["banho","cha","defumacao"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/8/82/Basil-Basilico-Ocimum_basilicum-albahaca.jpg/640px-Basil-Basilico-Ocimum_basilicum-albahaca.jpg"},

  {"name":"Canela","sci":"Cinnamomum verum","emoji":"🪵","temp":"quente","elem":"fogo","cat":"casca",
   "desc":"Especiaria de calor e atração, aceleradora de manifestações espirituais e prosperidade.",
   "spiritual":"Acelera manifestações, atrai prosperidade, amor e sorte. Ligada ao fogo de Xangô.",
   "bath_uses":["Atração","Prosperidade","Amor","Aquecimento espiritual"],"tea_uses":["Foco","Força","Circulação"],
   "can_fumigate":True,"fumig":"Defumação de prosperidade e atração com aroma marcante.",
   "orixas":["Oxum","Xangô"],"compat":["Cravo","Manjericão","Rosa Vermelha","Gengibre"],
   "incompat":[],"preparo":"Use em pau ou pó. Cuidado em banhos de criança.",
   "recommended":["banho","cha","defumacao"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/4/4e/Cinnamon-other.jpg/640px-Cinnamon-other.jpg"},

  {"name":"Jasmim","sci":"Jasminum officinale","emoji":"🌸","temp":"fria","elem":"água","cat":"flor",
   "desc":"Flor suave de amor puro e conexão com o feminino sagrado. Aroma que eleva e tranquiliza.",
   "spiritual":"Serenidade, amor puro e profunda conexão com Iemanjá e Oxum.",
   "bath_uses":["Amor","Paz","Feminino sagrado","Sono"],"tea_uses":["Relaxamento","Sono","Calma"],
   "can_fumigate":True,"fumig":"Defumação doce para amor, harmonia e meditação.",
   "orixas":["Iemanjá","Oxum"],"compat":["Rosa Branca","Lavanda","Alfazema","Camomila"],
   "incompat":["Guiné","Arruda"],"preparo":"Fresco em sachês ou chás. Aroma intenso — use com moderação.",
   "recommended":["banho","cha","defumacao"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/f/fb/Jasmine_flower.jpg/640px-Jasmine_flower.jpg"},

  {"name":"Colônia","sci":"Alpinia zerumbet","emoji":"🌺","temp":"quente","elem":"água","cat":"flor",
   "desc":"Erva de Oxum muito usada em banhos de amor, atração e abertura para o bem.",
   "spiritual":"Vibração elevada de amor, prosperidade e harmonia. Erva predileta de Oxum.",
   "bath_uses":["Amor","Atração","Prosperidade","Abertura para o bem"],"tea_uses":[],
   "can_fumigate":True,"fumig":"Defumação suave e perfumada de harmonia e amor.",
   "orixas":["Oxum","Iemanjá"],"compat":["Manjericão","Rosa Vermelha","Canela","Patchouli"],
   "incompat":[],"preparo":"Flores e folhas frescas em banhos de Oxum. Use às sextas-feiras.",
   "recommended":["banho","defumacao"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/5/53/Alpinia_zerumbet_%28Shell_ginger%29.jpg/640px-Alpinia_zerumbet_%28Shell_ginger%29.jpg"},

  {"name":"Rosa Amarela","sci":"Rosa × hybrida (amarela)","emoji":"🌼","temp":"quente","elem":"fogo","cat":"flor",
   "desc":"Flor solar de prosperidade, amizade e alegria espiritual, ligada a Oxum e Xangô.",
   "spiritual":"Atração de prosperidade, alegria e amizades verdadeiras.",
   "bath_uses":["Prosperidade","Alegria","Amizade","Sucesso"],"tea_uses":[],
   "can_fumigate":False,"fumig":"","orixas":["Oxum","Xangô"],
   "compat":["Canela","Calêndula","Rosa Vermelha","Girassol"],"incompat":[],
   "preparo":"Pétalas frescas em banhos de prosperidade às sextas-feiras.",
   "recommended":["banho"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/1/19/Yellow_Rose.jpg/640px-Yellow_Rose.jpg"},

  {"name":"Patchouli","sci":"Pogostemon cablin","emoji":"🟤","temp":"quente","elem":"terra","cat":"erva",
   "desc":"Erva enraizada de aroma forte que atrai prosperidade material e fortalece laços afetivos.",
   "spiritual":"Estabilidade, enraizamento, prosperidade e atração sensual. Ligada à terra e a Exu.",
   "bath_uses":["Enraizamento","Prosperidade","Sensualidade","Atração"],"tea_uses":[],
   "can_fumigate":True,"fumig":"Defumação de enraizamento, prosperidade e sensualidade.",
   "orixas":["Oxum","Exu"],"compat":["Canela","Manjericão","Colônia"],
   "incompat":[],"preparo":"Usado seco ou em óleo. Ótimo para banhos de Lua Cheia.",
   "recommended":["banho","defumacao"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/1/1a/Pogostemon_cablin.jpg/640px-Pogostemon_cablin.jpg"},

  {"name":"Macaça","sci":"Petrea volubilis","emoji":"💜","temp":"fria","elem":"água","cat":"flor",
   "desc":"Planta trepadeira de flores lilás ligada a Oxum e Iemanjá, usada em banhos de beleza e amor.",
   "spiritual":"Amor, beleza espiritual e atração afetiva.",
   "bath_uses":["Amor","Beleza espiritual","Atração"],"tea_uses":[],
   "can_fumigate":False,"fumig":"","orixas":["Oxum","Iemanjá"],
   "compat":["Colônia","Rosa Vermelha","Jasmim"],"incompat":[],
   "preparo":"Flores em banhos de amor de Oxum às sextas-feiras.",
   "recommended":["banho"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/b/bd/Petrea_volubilis.jpg/640px-Petrea_volubilis.jpg"},

  # ════════════════════════════════════════════════════════════
  # GRUPO 3 – Paz, cura e equilíbrio
  # ════════════════════════════════════════════════════════════
  {"name":"Camomila","sci":"Matricaria chamomilla","emoji":"🌼","temp":"fria","elem":"água","cat":"flor",
   "desc":"Flor suave de cura emocional, sono tranquilo e proteção gentil, especialmente para crianças.",
   "spiritual":"Calmaria, proteção e cura de crianças. Erva das mães espirituais.",
   "bath_uses":["Cura","Paz","Proteção infantil","Relaxamento"],"tea_uses":["Sono","Relaxamento","Cólica"],
   "can_fumigate":True,"fumig":"Defumação delicada para ambientes de cura e descanso.",
   "orixas":["Oxalá","Iemanjá","Oxum"],"compat":["Lavanda","Alfazema","Jasmim","Erva-Cidreira"],
   "incompat":[],"preparo":"Segura para crianças e gestantes em chá e banho.",
   "recommended":["banho","cha","defumacao"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/3/33/Chamomile%40original_size.jpg/640px-Chamomile%40original_size.jpg"},

  {"name":"Lavanda","sci":"Lavandula angustifolia","emoji":"💜","temp":"fria","elem":"ar","cat":"flor",
   "desc":"Flor da paz e clareza espiritual, usada para trazer sono tranquilo e limpeza suave da aura.",
   "spiritual":"Sono tranquilo, serenidade profunda e limpeza suave do campo áurico.",
   "bath_uses":["Paz","Sono","Purificação","Equilíbrio"],"tea_uses":["Calma","Sono","Ansiedade"],
   "can_fumigate":True,"fumig":"Defumação relaxante para ambientes de cura e terapia.",
   "orixas":["Oxalá","Iemanjá"],"compat":["Alfazema","Jasmim","Camomila","Verbena"],
   "incompat":["Arruda","Guiné"],"preparo":"Seca ou fresca, ideal para travesseiros, sachês e chás.",
   "recommended":["banho","cha","defumacao"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/7/7b/Lavande_en_fleurs.jpg/640px-Lavande_en_fleurs.jpg"},

  {"name":"Erva-Cidreira","sci":"Melissa officinalis","emoji":"🌿","temp":"fria","elem":"água","cat":"erva",
   "desc":"Erva da paz mental e equilíbrio emocional. Um dos chás mais seguros e versáteis da umbanda.",
   "spiritual":"Clareza emocional, cura mental e equilíbrio do sistema nervoso sutil.",
   "bath_uses":["Equilíbrio","Paz","Cura emocional","Ansiedade"],"tea_uses":["Tranquilidade","Calma","Insônia"],
   "can_fumigate":True,"fumig":"Defumação para equilíbrio emocional e descanso profundo.",
   "orixas":["Oxalá","Iemanjá"],"compat":["Camomila","Lavanda","Capim-Limão","Maracujá"],
   "incompat":[],"preparo":"Fresco ou seco. Chá diário sem contraindicações.",
   "recommended":["banho","cha","defumacao"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/5/58/Melissa_officinalis_001.JPG/640px-Melissa_officinalis_001.JPG"},

  {"name":"Alfazema","sci":"Lavandula spica","emoji":"💜","temp":"fria","elem":"ar","cat":"flor",
   "desc":"Prima da lavanda, com aroma suave que traz paz, equilíbrio e proteção delicada.",
   "spiritual":"Equilíbrio espiritual, proteção delicada e abertura para comunicação mediúnica.",
   "bath_uses":["Paz","Limpeza suave","Equilíbrio"],"tea_uses":["Relaxamento","Sono","Clareza"],
   "can_fumigate":True,"fumig":"Defumação de paz, proteção suave e elevação espiritual.",
   "orixas":["Oxalá","Iemanjá"],"compat":["Lavanda","Camomila","Erva-Cidreira","Verbena"],
   "incompat":[],"preparo":"Pode ser usada em sachês e travesseiros. Excelente para benzeduras.",
   "recommended":["banho","cha","defumacao"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/a/a4/Lavandula_spica_MHNT.BOT.2006.0.101.jpg/640px-Lavandula_spica_MHNT.BOT.2006.0.101.jpg"},

  {"name":"Maracujá","sci":"Passiflora edulis","emoji":"🌺","temp":"fria","elem":"água","cat":"flor",
   "desc":"Flor e fruta que trazem paz profunda, cura emocional e sono reparador.",
   "spiritual":"Equilíbrio emocional, liberação de tensões e cura do sistema nervoso sutil.",
   "bath_uses":["Paz","Sono","Equilíbrio emocional"],"tea_uses":["Calma","Sono","Ansiedade"],
   "can_fumigate":False,"fumig":"","orixas":["Iemanjá","Oxum"],
   "compat":["Erva-Cidreira","Camomila","Alfazema","Mulungu"],"incompat":[],
   "preparo":"Flores e folhas em chá ou banho. Muito seguro para uso diário.",
   "recommended":["banho","cha"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/1/1f/Passion_flower.jpg/640px-Passion_flower.jpg"},

  {"name":"Capim-Limão","sci":"Cymbopogon citratus","emoji":"🌾","temp":"morna","elem":"ar","cat":"erva",
   "desc":"Erva leve e refrescante de limpeza, frescor e alegria espiritual para o dia a dia.",
   "spiritual":"Renovação, leveza e limpeza energética suave.",
   "bath_uses":["Limpeza","Alegria","Renovação"],"tea_uses":["Frescura","Calma","Digestão"],
   "can_fumigate":True,"fumig":"Defumação leve e refrescante para ambientes de trabalho.",
   "orixas":["Oxalá","Iemanjá"],"compat":["Hortelã","Alfazema","Erva-Cidreira","Capim-Santo"],
   "incompat":[],"preparo":"Banhos diários de manutenção e chás suaves sem contraindicações.",
   "recommended":["banho","cha","defumacao"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/9/91/Cymbopogon_citratus.jpg/640px-Cymbopogon_citratus.jpg"},

  {"name":"Capim-Santo","sci":"Cymbopogon nardus","emoji":"🌾","temp":"morna","elem":"ar","cat":"erva",
   "desc":"Erva de cheiro suave ligada a Oxalá, muito usada em banhos de manutenção e chás de paz.",
   "spiritual":"Paz, leveza e proteção suave do ambiente espiritual.",
   "bath_uses":["Paz","Manutenção energética","Leveza"],"tea_uses":["Calma","Sono","Digestão"],
   "can_fumigate":True,"fumig":"Defumação suave para manutenção vibracional do lar.",
   "orixas":["Oxalá","Iemanjá"],"compat":["Capim-Limão","Erva-Cidreira","Alfazema"],
   "incompat":[],"preparo":"Ideal para chás diários de manutenção espiritual.",
   "recommended":["banho","cha","defumacao"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/8/87/Cymbopogon_nardus.jpg/640px-Cymbopogon_nardus.jpg"},

  {"name":"Verbena","sci":"Verbena officinalis","emoji":"💜","temp":"fria","elem":"água","cat":"erva",
   "desc":"Erva de encantamento e comunicação espiritual, usada em sessões mediúnicas e banhos de luz.",
   "spiritual":"Clarividência, desenvolvimento mediúnico e diálogo com guias espirituais.",
   "bath_uses":["Comunicação espiritual","Desenvolvimento mediúnico","Encantamento"],"tea_uses":["Tranquilidade","Clareza"],
   "can_fumigate":True,"fumig":"Defumação para sessões mediúnicas e trabalhos de clarividência.",
   "orixas":["Iemanjá","Oxalá"],"compat":["Alfazema","Lavanda","Jasmim"],
   "incompat":[],"preparo":"Fresco ou seco. Ideal antes de médiuns abrirem trabalho.",
   "recommended":["banho","cha","defumacao"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/1/18/Verbena_officinalis_1.jpg/640px-Verbena_officinalis_1.jpg"},

  {"name":"Erva-Doce","sci":"Foeniculum vulgare","emoji":"🌿","temp":"morna","elem":"água","cat":"semente",
   "desc":"Erva adocicada de harmonia e equilíbrio emocional. Muito usada em crianças com cólica.",
   "spiritual":"Harmonia, doçura nas relações e equilíbrio do ambiente espiritual.",
   "bath_uses":["Harmonia","Equilíbrio","Doçura"],"tea_uses":["Digestão","Calma","Cólica"],
   "can_fumigate":True,"fumig":"Defumação suave e adocicada para harmonia do lar.",
   "orixas":["Oxalá","Oxum"],"compat":["Capim-Limão","Erva-Cidreira","Camomila"],
   "incompat":[],"preparo":"Sementes em chá ou banho. Muito usado para crianças com cólica.",
   "recommended":["banho","cha","defumacao"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/3/31/Fennel_seeds.jpg/640px-Fennel_seeds.jpg"},

  {"name":"Manacá","sci":"Brunfelsia uniflora","emoji":"🌸","temp":"fria","elem":"água","cat":"flor",
   "desc":"Flor de Oxalá e Nanã para cura espiritual, equilíbrio e suavização das cargas kármicas.",
   "spiritual":"Equilíbrio, cura kármica e suavização de karmas difíceis.",
   "bath_uses":["Cura","Equilíbrio kármico","Suavização"],"tea_uses":[],
   "can_fumigate":True,"fumig":"Defumação para cura espiritual profunda e equilíbrio.",
   "orixas":["Oxalá","Nanã"],"compat":["Alfazema","Camomila","Rosa Branca"],
   "incompat":[],"preparo":"Use com cuidado — planta de uso ritual. Consulte um pai/mãe de santo.",
   "recommended":["banho"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/8/88/Brunfelsia_uniflora_-_Flickr_-_Dick_Culbert.jpg/640px-Brunfelsia_uniflora_-_Flickr_-_Dick_Culbert.jpg"},

  {"name":"Mulungu","sci":"Erythrina verna","emoji":"🌳","temp":"fria","elem":"água","cat":"casca",
   "desc":"Casca sagrada de Xangô para cura, equilíbrio nervoso e sono profundo.",
   "spiritual":"Equilíbrio, cura do sistema nervoso e força de Xangô.",
   "bath_uses":["Equilíbrio nervoso","Cura","Sono"],"tea_uses":["Ansiedade","Sono","Equilíbrio nervoso"],
   "can_fumigate":False,"fumig":"","orixas":["Xangô"],
   "compat":["Maracujá","Erva-Cidreira","Camomila"],"incompat":[],
   "preparo":"Casca em chá ou banho. Contraindicado em gestantes e crianças.",
   "recommended":["banho","cha"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/4/48/Erythrina_verna.jpg/640px-Erythrina_verna.jpg"},

  # ════════════════════════════════════════════════════════════
  # GRUPO 4 – Força, vitória e abertura de caminhos
  # ════════════════════════════════════════════════════════════
  {"name":"Alecrim","sci":"Rosmarinus officinalis","emoji":"🌱","temp":"quente","elem":"fogo","cat":"erva",
   "desc":"Erva do sol que fortalece a mente, afasta inveja, abre caminhos. Indispensável no abo e descarrego.",
   "spiritual":"Purificação, proteção e aumento da clareza espiritual. Destruidor eficiente de larvas astrais.",
   "bath_uses":["Proteção","Abertura de caminhos","Descarrego","Força","Limpeza"],"tea_uses":["Clareza","Proteção","Tosse"],
   "can_fumigate":True,"fumig":"Defumação purificadora clássica para ambientes e altares.",
   "orixas":["Oxalá","Ogum"],"compat":["Arruda","Manjericão","Alfazema","Sálvia"],
   "incompat":[],"preparo":"Fresco ou seco em banho, chá e defumação. Parte indispensável do abo.",
   "recommended":["banho","defumacao"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/4/4a/Rosemary_bush.jpg/640px-Rosemary_bush.jpg"},

  {"name":"Hortelã","sci":"Mentha × piperita","emoji":"🌿","temp":"fria","elem":"ar","cat":"erva",
   "desc":"Erva refrescante que traz clareza mental, abre caminhos e atrai prosperidade.",
   "spiritual":"Clareza, renovação energética, prosperidade e força de concentração.",
   "bath_uses":["Prosperidade","Renovação","Clareza","Concentração"],"tea_uses":["Foco","Calma","Digestão","Respiração"],
   "can_fumigate":True,"fumig":"Defumação energizante para estudos, negócios e trabalho.",
   "orixas":["Oxalá","Oxóssi"],"compat":["Alecrim","Capim-Limão","Erva-Cidreira"],
   "incompat":[],"preparo":"Fresco ou seco, ideal para chás e banhos refrescantes diários.",
   "recommended":["banho","cha","defumacao"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/9/99/Peppermint_in_a_pot.jpg/640px-Peppermint_in_a_pot.jpg"},

  {"name":"Cravo","sci":"Syzygium aromaticum","emoji":"🌸","temp":"quente","elem":"fogo","cat":"flor",
   "desc":"Especiaria de poder espiritual que traz justiça, proteção e abertura de caminhos.",
   "spiritual":"Proteção, força de manifestação e vibração sacramental ligada a Xangô.",
   "bath_uses":["Proteção","Justiça","Prosperidade","Força"],"tea_uses":["Força","Clareza","Imunidade"],
   "can_fumigate":True,"fumig":"Defumação de proteção forte e estabilidade espiritual.",
   "orixas":["Xangô","Exu"],"compat":["Canela","Pimenta-da-Guiné","Gengibre"],
   "incompat":["Jasmim"],"preparo":"Use com moderação em banhos e defumações. Aroma intenso.",
   "recommended":["banho","cha","defumacao"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/Cloves_macro.jpg/640px-Cloves_macro.jpg"},

  {"name":"Louro","sci":"Laurus nobilis","emoji":"🌿","temp":"quente","elem":"fogo","cat":"folha",
   "desc":"Erva solar de vitória, proteção e consagração espiritual. Ligada a Oxóssi e Xangô.",
   "spiritual":"Sucesso em disputas, vitória e proteção espiritual.",
   "bath_uses":["Vitória","Consagração","Proteção","Sucesso"],"tea_uses":["Força","Clareza","Digestão"],
   "can_fumigate":True,"fumig":"Defumação de vitória para momentos decisivos e consagrações.",
   "orixas":["Oxóssi","Xangô"],"compat":["Alecrim","Cravo","Gengibre","Sálvia"],
   "incompat":[],"preparo":"Folhas frescas ou secas em banhos de consagração e vitória.",
   "recommended":["banho","cha","defumacao"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/3/33/Laurus_nobilis_-_K%C3%B6hler%E2%80%93s_Medizinal-Pflanzen-081.jpg/640px-Laurus_nobilis_-_K%C3%B6hler%E2%80%93s_Medizinal-Pflanzen-081.jpg"},

  {"name":"Gengibre","sci":"Zingiber officinale","emoji":"🫚","temp":"quente","elem":"fogo","cat":"raiz",
   "desc":"Raiz ardente que ativa força física e espiritual, coragem e aceleração de manifestações.",
   "spiritual":"Ativação, coragem, fogo interior e aceleração de processos espirituais.",
   "bath_uses":["Força","Ativação","Saúde","Coragem"],"tea_uses":["Aquecimento","Força","Imunidade","Digestão"],
   "can_fumigate":True,"fumig":"Defumação ativadora para trabalhos de energia e força.",
   "orixas":["Ogum","Xangô"],"compat":["Canela","Cravo","Louro","Pimenta-da-Guiné"],
   "incompat":[],"preparo":"Rale ou corte em lascas. Pode tingir o banho levemente de amarelo.",
   "recommended":["banho","cha","defumacao"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/2/25/GingerRoots.jpg/640px-GingerRoots.jpg"},

  {"name":"Pimenta-da-Guiné","sci":"Aframomum melegueta","emoji":"🌶️","temp":"quente","elem":"fogo","cat":"semente",
   "desc":"Semente de poder ligada a Exu para proteção, força e abertura de caminhos bloqueados.",
   "spiritual":"Força, coragem, desobstrução energética e abertura de caminhos.",
   "bath_uses":["Força","Abertura de caminhos","Proteção","Coragem"],"tea_uses":[],
   "can_fumigate":True,"fumig":"Defumação poderosa para romper bloqueios e desobstruir caminhos.",
   "orixas":["Exu","Ogum"],"compat":["Arruda","Cravo","Guiné","Gengibre"],
   "incompat":["Lavanda","Camomila"],"preparo":"Usar com moderação; pode irritar pele sensível.",
   "recommended":["banho","defumacao"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/8/8a/Aframomum_melegueta.jpg/640px-Aframomum_melegueta.jpg"},

  {"name":"Sálvia","sci":"Salvia officinalis","emoji":"🌿","temp":"quente","elem":"fogo","cat":"erva",
   "desc":"Erva de sabedoria ancestral, proteção e purificação duradoura de ambientes e pessoas.",
   "spiritual":"Limpeza profunda, sabedoria e conexão com rituais de consagração.",
   "bath_uses":["Purificação","Sabedoria","Consagração"],"tea_uses":["Clareza","Proteção","Foco"],
   "can_fumigate":True,"fumig":"Defumação clássica de limpeza profunda para ambientes.",
   "orixas":["Oxalá","Ogum"],"compat":["Alecrim","Arruda","Louro","Incenso (Olíbano)"],
   "incompat":[],"preparo":"Fresco ou seco. Use em defumações longas para limpeza de terreiros.",
   "recommended":["banho","cha","defumacao"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/3/31/Salvia_officinalis_0.jpg/640px-Salvia_officinalis_0.jpg"},

  {"name":"Carqueja","sci":"Baccharis trimera","emoji":"🌿","temp":"quente","elem":"fogo","cat":"erva",
   "desc":"Erva amarga e purificadora de Xangô e Ogum, usada em banhos de descarrego e limpeza.",
   "spiritual":"Purificação intensa, corte de laços negativos e fortalecimento do campo áurico.",
   "bath_uses":["Descarrego","Purificação intensa","Corte de laços"],"tea_uses":["Fígado","Digestão"],
   "can_fumigate":True,"fumig":"Defumação para ambientes pesados e após conflitos.",
   "orixas":["Xangô","Ogum","Oxum"],"compat":["Arruda","Alecrim","Aroeira"],
   "incompat":[],"preparo":"Muito amarga. Em chá, use em pequenas doses. Contraindicada em gestantes.",
   "recommended":["banho","defumacao"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/e/e2/Baccharis_trimera.jpg/640px-Baccharis_trimera.jpg"},

  {"name":"Abre-Caminho","sci":"Zingiber zerumbet","emoji":"🌿","temp":"quente","elem":"fogo","cat":"erva",
   "desc":"Erva sagrada de Ogum e Oxóssi para romper bloqueios, abrir caminhos e trazer prosperidade.",
   "spiritual":"Desobstrução de caminhos bloqueados, prosperidade e sucesso em projetos.",
   "bath_uses":["Abertura de caminhos","Prosperidade","Desobstrução"],"tea_uses":[],
   "can_fumigate":True,"fumig":"Defumação para abrir caminhos antes de empreendimentos.",
   "orixas":["Ogum","Oxóssi","Exu"],"compat":["Alecrim","Louro","Arruda","Manjericão"],
   "incompat":[],"preparo":"Use fresco ou seco. Tome às terças-feiras para Ogum.",
   "recommended":["banho","defumacao"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/Zingiber_zerumbet.jpg/640px-Zingiber_zerumbet.jpg"},

  {"name":"Erva-Mate","sci":"Ilex paraguariensis","emoji":"🌿","temp":"quente","elem":"fogo","cat":"folha",
   "desc":"Erva energética do sul, símbolo de força, vitalidade e comunhão espiritual entre guerreiros.",
   "spiritual":"Energia, vitalidade e concentração. Ligada aos guerreiros espirituais.",
   "bath_uses":["Energia","Vitalidade","Força"],"tea_uses":["Vigor","Atenção","Energia"],
   "can_fumigate":True,"fumig":"Defumação de energia e clareza mental.",
   "orixas":["Ogum","Oxóssi"],"compat":["Alecrim","Louro","Gengibre"],
   "incompat":[],"preparo":"Erva em chá ou banho para energia e força física-espiritual.",
   "recommended":["banho","cha","defumacao"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/e/e0/Ilex_paraguariensis_%281%29.jpg/640px-Ilex_paraguariensis_%281%29.jpg"},

  # ════════════════════════════════════════════════════════════
  # GRUPO 5 – Resinas sagradas
  # ════════════════════════════════════════════════════════════
  {"name":"Incenso (Olíbano)","sci":"Boswellia sacra","emoji":"💨","temp":"quente","elem":"fogo","cat":"resina",
   "desc":"Resina ancestral sagrada para elevar vibrações, purificar ambientes e abrir sessões espirituais.",
   "spiritual":"Conexão espiritual profunda, purificação e elevação vibracional. Ligada a Oxalá.",
   "bath_uses":[],"tea_uses":[],
   "can_fumigate":True,"fumig":"Defumação sagrada para abertura de trabalhos espirituais e altares.",
   "orixas":["Oxalá"],"compat":["Mirra","Alecrim","Alfazema","Benjoim"],
   "incompat":[],"preparo":"Queime sobre brasa. Não use em banho. Ventile bem o ambiente.",
   "recommended":["defumacao"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/5/5e/Boswellia_sacra_tree.jpg/640px-Boswellia_sacra_tree.jpg"},

  {"name":"Mirra","sci":"Commiphora myrrha","emoji":"🔶","temp":"quente","elem":"fogo","cat":"resina",
   "desc":"Resina bíblica de purificação profunda, força espiritual e conexão com ancestrais.",
   "spiritual":"Proteção profunda, força espiritual e limpeza de karma. Ligada a Oxalá e Omolu.",
   "bath_uses":[],"tea_uses":[],
   "can_fumigate":True,"fumig":"Defumação de purificação ancestral e elevação espiritual profunda.",
   "orixas":["Oxalá","Omolu"],"compat":["Incenso (Olíbano)","Alecrim","Benjoim","Cedro"],
   "incompat":[],"preparo":"Use somente em defumações sobre brasa. Não misture com água.",
   "recommended":["defumacao"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/b/b4/MyrrheSmall.jpg/640px-MyrrheSmall.jpg"},

  {"name":"Benjoim","sci":"Styrax benzoin","emoji":"🟤","temp":"quente","elem":"fogo","cat":"resina",
   "desc":"Resina balsâmica e adocicada para consagrar espaços, instrumentos rituais e altares.",
   "spiritual":"Consagração, elevação vibracional e proteção de espaços sagrados.",
   "bath_uses":[],"tea_uses":[],
   "can_fumigate":True,"fumig":"Defumação de consagração e elevação para altares e espaços sagrados.",
   "orixas":["Oxalá"],"compat":["Incenso (Olíbano)","Mirra","Alfazema"],
   "incompat":[],"preparo":"Queime em defumações para consagrar o ambiente ritual.",
   "recommended":["defumacao"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/5/58/Styrax_benzoin.jpg/640px-Styrax_benzoin.jpg"},

  {"name":"Copaíba","sci":"Copaifera langsdorffii","emoji":"🟤","temp":"quente","elem":"fogo","cat":"resina",
   "desc":"Resina amazônica sagrada para cura, proteção da floresta e renovação espiritual.",
   "spiritual":"Proteção da mata, cura ancestral e conexão com os espíritos da floresta.",
   "bath_uses":["Cura","Proteção"],"tea_uses":[],
   "can_fumigate":True,"fumig":"Defumação da floresta, cura e proteção ancestral.",
   "orixas":["Oxóssi","Omolu"],"compat":["Espinheira-Santa","Jurema Preta","Cedro"],
   "incompat":[],"preparo":"Resina em defumação para cura da natureza. Óleo usado externamente.",
   "recommended":["banho","defumacao"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/0/0d/Copaifera_langsdorffii.jpg/640px-Copaifera_langsdorffii.jpg"},

  {"name":"Sândalo","sci":"Santalum album","emoji":"🪵","temp":"fria","elem":"ar","cat":"casca",
   "desc":"Madeira sagrada de meditação, elevação espiritual e conexão com planos superiores.",
   "spiritual":"Meditação, elevação espiritual e purificação da mente e do coração.",
   "bath_uses":["Meditação","Elevação","Purificação mental"],"tea_uses":[],
   "can_fumigate":True,"fumig":"Defumação sagrada de meditação e elevação espiritual.",
   "orixas":["Oxalá"],"compat":["Incenso (Olíbano)","Alfazema","Mirra"],
   "incompat":[],"preparo":"Principalmente usado em defumações. Óleo para unção ritual.",
   "recommended":["defumacao"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/3/34/Sandalwood.jpg/640px-Sandalwood.jpg"},

  {"name":"Alcanfor","sci":"Cinnamomum camphora","emoji":"🌿","temp":"fria","elem":"ar","cat":"resina",
   "desc":"Resina cristalina de limpeza intensa do ambiente e afastamento rápido de energias negativas.",
   "spiritual":"Limpeza rápida e intensa de ambientes carregados.",
   "bath_uses":["Limpeza rápida","Descarrego"],"tea_uses":[],
   "can_fumigate":True,"fumig":"Defumação de limpeza rápida e intensa para ambientes pesados.",
   "orixas":["Ogum","Exu"],"compat":["Alecrim","Arruda"],
   "incompat":[],"preparo":"Nunca ingerir. Use em defumações ou banhos com muito cuidado.",
   "recommended":["defumacao"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/8/8e/Camphor_crystals.jpg/640px-Camphor_crystals.jpg"},

  # ════════════════════════════════════════════════════════════
  # GRUPO 6 – Oxalá, pureza e elevação
  # ════════════════════════════════════════════════════════════
  {"name":"Rosa Branca","sci":"Rosa × hybrida (branca)","emoji":"🤍","temp":"fria","elem":"água","cat":"flor",
   "desc":"Flor de pureza absoluta, paz e conexão com os planos mais elevados. Consagrada a Oxalá.",
   "spiritual":"Elevação espiritual, pureza e proteção angelical dos filhos de Oxalá.",
   "bath_uses":["Pureza","Paz","Elevação espiritual"],"tea_uses":[],
   "can_fumigate":False,"fumig":"","orixas":["Oxalá"],
   "compat":["Jasmim","Camomila","Alfazema"],"incompat":["Guiné","Arruda","Pinhão Roxo"],
   "preparo":"Pétalas frescas em banhos de elevação. Use às domingos.",
   "recommended":["banho"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/4/40/White_Rose_Bud.jpg/640px-White_Rose_Bud.jpg"},

  {"name":"Boldo","sci":"Plectranthus barbatus","emoji":"🌿","temp":"neutra","elem":"terra","cat":"folha",
   "desc":"Folha amarga de proteção e cura, muito usada em banhos de Oxalá e descarrego suave.",
   "spiritual":"Cura espiritual, proteção e limpeza suave para filhos de Oxalá.",
   "bath_uses":["Cura","Proteção","Descarrego suave"],"tea_uses":["Fígado","Digestão","Cura"],
   "can_fumigate":True,"fumig":"Defumação suave para ambientes de cura espiritual.",
   "orixas":["Oxalá","Xangô"],"compat":["Alecrim","Alfazema","Camomila"],
   "incompat":[],"preparo":"Folhas frescas em chá para cura do fígado. Moderação em gestantes.",
   "recommended":["banho","cha"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/3/3d/Plectranthus_barbatus_-_K%C3%B6hler%E2%80%93s_Medizinal-Pflanzen-264.jpg/640px-Plectranthus_barbatus_-_K%C3%B6hler%E2%80%93s_Medizinal-Pflanzen-264.jpg"},

  {"name":"Angélica","sci":"Angelica archangelica","emoji":"🌿","temp":"quente","elem":"fogo","cat":"raiz",
   "desc":"Raiz dos anjos que protege e abre portas espirituais para os planos mais elevados.",
   "spiritual":"Proteção angelical, clareza espiritual e conexão com guias de luz.",
   "bath_uses":["Proteção","Abertura espiritual","Conexão com anjos"],"tea_uses":["Força","Proteção"],
   "can_fumigate":True,"fumig":"Defumação de proteção angelical e elevação espiritual.",
   "orixas":["Oxalá"],"compat":["Incenso (Olíbano)","Mirra","Alfazema"],
   "incompat":[],"preparo":"Raiz seca em chá ou defumação. Contraindicada em gestantes.",
   "recommended":["banho","defumacao"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/5/51/Angelica_archangelica_blueten.jpg/640px-Angelica_archangelica_blueten.jpg"},

  {"name":"Algodão","sci":"Gossypium herbaceum","emoji":"🤍","temp":"fria","elem":"água","cat":"flor",
   "desc":"Planta sagrada de Oxalá, símbolo de pureza. Usada em rituais, velas e banhos de paz.",
   "spiritual":"Pureza, paz e conexão com Oxalá. O algodão é símbolo sagrado de Oxalá na Umbanda.",
   "bath_uses":["Pureza","Paz","Conexão com Oxalá"],"tea_uses":[],
   "can_fumigate":False,"fumig":"","orixas":["Oxalá"],
   "compat":["Rosa Branca","Alfazema","Lírio Branco"],"incompat":["Guiné","Arruda"],
   "preparo":"Flocos de algodão em banhos de Oxalá. Muito usado em obrigações.",
   "recommended":["banho"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/a/a9/CottonPlant.JPG/640px-CottonPlant.JPG"},

  {"name":"Lírio Branco","sci":"Lilium candidum","emoji":"🤍","temp":"fria","elem":"água","cat":"flor",
   "desc":"Flor de pureza absoluta usada em banhos de elevação espiritual e conexão com Oxalá.",
   "spiritual":"Pureza, elevação e conexão com os planos mais elevados.",
   "bath_uses":["Pureza","Elevação","Conexão espiritual"],"tea_uses":[],
   "can_fumigate":False,"fumig":"","orixas":["Oxalá","Iemanjá"],
   "compat":["Rosa Branca","Alfazema","Jasmim"],"incompat":["Arruda","Guiné"],
   "preparo":"Pétalas frescas em banhos de elevação espiritual. Muito delicado.",
   "recommended":["banho"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/8/8e/Lilium_candidum_1.jpg/640px-Lilium_candidum_1.jpg"},

  # ════════════════════════════════════════════════════════════
  # GRUPO 7 – Oxóssi e a mata sagrada
  # ════════════════════════════════════════════════════════════
  {"name":"Jurema Preta","sci":"Mimosa tenuiflora","emoji":"🌿","temp":"quente","elem":"terra","cat":"casca",
   "desc":"Árvore sagrada para conexão com os ancestrais da mata, caboclos e linhas de Oxóssi.",
   "spiritual":"Conexão com guias ancestrais, visão espiritual e poder da mata sagrada.",
   "bath_uses":["Conexão ancestral","Visão espiritual","Força da mata"],"tea_uses":[],
   "can_fumigate":True,"fumig":"Defumação para trabalhos de jurema e conexão com a mata.",
   "orixas":["Oxóssi","Exu"],"compat":["Incenso (Olíbano)","Cedro","Copaíba"],
   "incompat":[],"preparo":"Casca em banho ou defumação. Use com respeito à tradição sagrada.",
   "recommended":["banho","defumacao"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/8/8f/Mimosa_tenuiflora.jpg/640px-Mimosa_tenuiflora.jpg"},

  {"name":"Eucalipto","sci":"Eucalyptus globulus","emoji":"🌿","temp":"quente","elem":"ar","cat":"folha",
   "desc":"Folha que limpa o ar, fortalece a respiração, purifica ambientes e abre caminhos.",
   "spiritual":"Purificação, clareza nos caminhos da mente e abertura de bloqueios sutis.",
   "bath_uses":["Purificação","Cura","Clareza","Abertura de caminhos"],"tea_uses":["Respiração","Frescura","Imunidade"],
   "can_fumigate":True,"fumig":"Defumação purificadora para ambientes saturados e doentes.",
   "orixas":["Oxóssi","Ogum"],"compat":["Alecrim","Arruda","Sálvia"],
   "incompat":[],"preparo":"Folhas em banho ou vaporização para vias respiratórias.",
   "recommended":["banho","defumacao"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/a/a5/Eucalyptus_sp.jpg/640px-Eucalyptus_sp.jpg"},

  {"name":"Samambaia","sci":"Nephrolepis exaltata","emoji":"🌿","temp":"fria","elem":"água","cat":"folha",
   "desc":"Planta da mata de Oxóssi usada em banhos de proteção e conexão com os espíritos da floresta.",
   "spiritual":"Proteção da mata, equilíbrio e conexão com os caboclos e Oxóssi.",
   "bath_uses":["Proteção da mata","Equilíbrio","Conexão com caboclos"],"tea_uses":[],
   "can_fumigate":False,"fumig":"","orixas":["Oxóssi"],
   "compat":["Louro","Eucalipto","Capim-Limão"],"incompat":[],
   "preparo":"Folhas frescas em banhos de floresta. Manter em casa atrai boas energias.",
   "recommended":["banho"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/9/9d/Nephrolepis_exaltata.jpg/640px-Nephrolepis_exaltata.jpg"},

  {"name":"Cedro","sci":"Cedrus libani","emoji":"🌲","temp":"quente","elem":"fogo","cat":"casca",
   "desc":"Madeira sagrada de proteção ancestral e espiritualidade elevada.",
   "spiritual":"Conexão com ancestrais, proteção residencial e força espiritual.",
   "bath_uses":["Proteção","Espiritualidade","Ancestralidade"],"tea_uses":[],
   "can_fumigate":True,"fumig":"Defumação ancestral para centros espirituais e terreiros.",
   "orixas":["Xangô","Oxalá"],"compat":["Incenso (Olíbano)","Mirra","Jurema Preta"],
   "incompat":[],"preparo":"Cascas em defumação ou banhos consagrados de abertura.",
   "recommended":["banho","defumacao"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/7/76/Cedrus_libani_2.jpg/640px-Cedrus_libani_2.jpg"},

  {"name":"Espinheira-Santa","sci":"Maytenus ilicifolia","emoji":"🌿","temp":"neutra","elem":"terra","cat":"folha",
   "desc":"Planta sagrada da mata para cura, proteção e comunhão com os orixás da floresta.",
   "spiritual":"Cura espiritual, proteção da floresta e conexão com Oxóssi e Omolu.",
   "bath_uses":["Cura","Proteção da mata","Saúde"],"tea_uses":["Estômago","Úlcera","Cura"],
   "can_fumigate":True,"fumig":"Defumação de cura e proteção da natureza.",
   "orixas":["Oxóssi","Omolu"],"compat":["Copaíba","Jurema Preta","Cedro"],
   "incompat":[],"preparo":"Folhas em chá para cura. Em banho para proteção da saúde espiritual.",
   "recommended":["banho","cha"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/2/22/Maytenus_ilicifolia.jpg/640px-Maytenus_ilicifolia.jpg"},

  {"name":"Cipó-Caboclo","sci":"Sclerolobium paniculatum","emoji":"🌿","temp":"quente","elem":"terra","cat":"casca",
   "desc":"Planta da mata de Oxóssi usada pelos caboclos para proteção e força da floresta.",
   "spiritual":"Força dos caboclos e proteção da mata sagrada.",
   "bath_uses":["Força dos caboclos","Proteção da mata"],"tea_uses":[],
   "can_fumigate":True,"fumig":"Defumação para invocar força dos caboclos e proteção da mata.",
   "orixas":["Oxóssi"],"compat":["Jurema Preta","Samambaia","Eucalipto"],
   "incompat":[],"preparo":"Casca em banho ou defumação com invocação aos caboclos.",
   "recommended":["banho","defumacao"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/8/85/Sclerolobium_paniculatum.jpg/640px-Sclerolobium_paniculatum.jpg"},

  {"name":"Jatobá","sci":"Hymenaea courbaril","emoji":"🌳","temp":"quente","elem":"terra","cat":"casca",
   "desc":"Árvore sagrada da mata, usada por Ogum para força, resistência e proteção.",
   "spiritual":"Força, resistência espiritual e proteção das matas sagradas.",
   "bath_uses":["Força","Resistência","Proteção"],"tea_uses":["Energia","Força","Tosse"],
   "can_fumigate":True,"fumig":"Defumação de força e resistência espiritual.",
   "orixas":["Ogum","Oxóssi"],"compat":["Cipó-Caboclo","Cedro","Eucalipto"],
   "incompat":[],"preparo":"Casca ou resina em banho e defumação. Chá para energia.",
   "recommended":["banho","cha","defumacao"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/5/5a/Hymenaea_courbaril.jpg/640px-Hymenaea_courbaril.jpg"},

  {"name":"Guaco","sci":"Mikania glomerata","emoji":"🌿","temp":"quente","elem":"ar","cat":"erva",
   "desc":"Erva da mata de Oxóssi para cura das vias respiratórias e proteção espiritual.",
   "spiritual":"Cura, proteção espiritual da mata e força dos caboclos.",
   "bath_uses":["Proteção da mata","Cura espiritual"],"tea_uses":["Bronquite","Tosse","Gripe"],
   "can_fumigate":True,"fumig":"Defumação de cura respiratória e proteção da mata.",
   "orixas":["Oxóssi"],"compat":["Assa-Peixe","Eucalipto"],
   "incompat":[],"preparo":"Folhas em xarope ou chá para tosse. Em banho para proteção.",
   "recommended":["banho","cha"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/6/65/Mikania_glomerata.jpg/640px-Mikania_glomerata.jpg"},

  # ════════════════════════════════════════════════════════════
  # GRUPO 8 – Xangô, Iansã e energia de fogo
  # ════════════════════════════════════════════════════════════
  {"name":"Calêndula","sci":"Calendula officinalis","emoji":"🌻","temp":"quente","elem":"fogo","cat":"flor",
   "desc":"Flor solar de cura, prosperidade e alegria. Energia do sol ligada a Xangô e Oxum.",
   "spiritual":"Proteção solar, atração de boas energias e cura com a energia do sol.",
   "bath_uses":["Cura","Proteção","Prosperidade solar"],"tea_uses":["Cura","Imunidade","Anti-inflamatório"],
   "can_fumigate":True,"fumig":"Defumação solar de alegria, proteção e cura.",
   "orixas":["Oxum","Xangô","Iansã"],"compat":["Canela","Manjericão","Rosa Amarela","Girassol"],
   "incompat":[],"preparo":"Flores em banho ao sol. Pode tingir a água de amarelo dourado.",
   "recommended":["banho","cha","defumacao"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/7/70/Calendula_officinalis_%28English_Garden%29.jpg/640px-Calendula_officinalis_%28English_Garden%29.jpg"},

  {"name":"Espada-de-Santa-Bárbara","sci":"Dracaena marginata","emoji":"🗡️","temp":"quente","elem":"fogo","cat":"folha",
   "desc":"Planta guerreira de Iansã, usada para proteção contra energias hostis e tempestades espirituais.",
   "spiritual":"Proteção de Iansã, força feminina e combate às energias hostis.",
   "bath_uses":["Proteção de Iansã","Força feminina","Proteção em tempestades"],"tea_uses":[],
   "can_fumigate":False,"fumig":"","orixas":["Iansã"],
   "compat":["Arruda","Espada-de-São-Jorge","Guiné"],"incompat":[],
   "preparo":"Folhas em banhos de Iansã especialmente às quartas-feiras.",
   "recommended":["banho"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/d/d5/Dracaena_marginata0.jpg/640px-Dracaena_marginata0.jpg"},

  {"name":"Peregum","sci":"Dracaena fragrans","emoji":"🌿","temp":"quente","elem":"fogo","cat":"folha",
   "desc":"Folha sagrada muito usada no candomblé e umbanda, ligada a Xangô e aos orixás guerreiros.",
   "spiritual":"Proteção guerreira, força e vibração de orixás de fogo. Muito usada em obrigações.",
   "bath_uses":["Força","Proteção","Obrigações","Guerreiros"],"tea_uses":[],
   "can_fumigate":False,"fumig":"","orixas":["Xangô","Ogum","Iansã"],
   "compat":["Arruda","Louro","Espada-de-São-Jorge"],"incompat":[],
   "preparo":"Folhas frescas em banhos de força e obrigações rituais.",
   "recommended":["banho"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/5/5c/Dracaena_fragrans_%27Massangeana%27.jpg/640px-Dracaena_fragrans_%27Massangeana%27.jpg"},

  {"name":"Hibisco","sci":"Hibiscus rosa-sinensis","emoji":"🌺","temp":"quente","elem":"fogo","cat":"flor",
   "desc":"Flor vibrante de Iansã e Iemanjá, usada para fortalecimento, amor e abertura espiritual.",
   "spiritual":"Força feminina, amor e abertura energética. Conecta com Iansã e Iemanjá.",
   "bath_uses":["Força feminina","Amor","Abertura espiritual"],"tea_uses":["Pressão arterial","Antioxidante"],
   "can_fumigate":False,"fumig":"","orixas":["Iansã","Iemanjá"],
   "compat":["Rosa Vermelha","Calêndula","Colônia"],"incompat":[],
   "preparo":"Flores em banhos e chás. A água do chá fica vermelha vibrante.",
   "recommended":["banho","cha"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/d/d5/Hibiscus_rosa-sinensis_1.jpg/640px-Hibiscus_rosa-sinensis_1.jpg"},

  {"name":"Girassol","sci":"Helianthus annuus","emoji":"🌻","temp":"quente","elem":"fogo","cat":"flor",
   "desc":"Flor do sol que atrai alegria, positividade, prosperidade e sucesso espiritual.",
   "spiritual":"Alegria, positividade, sucesso e conexão com o sol espiritual.",
   "bath_uses":["Alegria","Sucesso","Positividade","Prosperidade"],"tea_uses":["Energia","Ânimo"],
   "can_fumigate":False,"fumig":"","orixas":["Xangô","Oxum"],
   "compat":["Calêndula","Rosa Amarela","Canela"],"incompat":[],
   "preparo":"Pétalas frescas em banhos matinais de alegria e prosperidade.",
   "recommended":["banho","cha"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/4/40/Sunflower_sky_backdrop.jpg/640px-Sunflower_sky_backdrop.jpg"},

  {"name":"Angico","sci":"Anadenanthera colubrina","emoji":"🌳","temp":"quente","elem":"terra","cat":"casca",
   "desc":"Casca sagrada de Ogum e Xangô para proteção, cura e força espiritual intensa.",
   "spiritual":"Proteção, força espiritual e cura de Xangô e Ogum.",
   "bath_uses":["Proteção forte","Cura","Força"],"tea_uses":[],
   "can_fumigate":True,"fumig":"Defumação de força e proteção espiritual intensa.",
   "orixas":["Xangô","Ogum"],"compat":["Aroeira","Arruda","Cedro"],
   "incompat":[],"preparo":"Casca fervida em banho forte. Use do pescoço para baixo.",
   "recommended":["banho","defumacao"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/e/e2/Anadenanthera_colubrina.jpg/640px-Anadenanthera_colubrina.jpg"},

  {"name":"Taioba","sci":"Xanthosoma sagittifolium","emoji":"🌿","temp":"quente","elem":"terra","cat":"folha",
   "desc":"Folha sagrada de Ogum e Xangô, muito usada em obrigações e banhos de força.",
   "spiritual":"Força, determinação e proteção dos guerreiros espirituais.",
   "bath_uses":["Força","Proteção de guerreiros","Obrigações"],"tea_uses":[],
   "can_fumigate":False,"fumig":"","orixas":["Ogum","Xangô"],
   "compat":["Arruda","Peregum","Louro"],"incompat":[],
   "preparo":"Folha em banho. Não ingira crua — contém ácido oxálico.",
   "recommended":["banho"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/b/b0/Xanthosoma_sagittifolium_-_K%C3%B6hler%E2%80%93s_Medizinal-Pflanzen-199.jpg/640px-Xanthosoma_sagittifolium_-_K%C3%B6hler%E2%80%93s_Medizinal-Pflanzen-199.jpg"},

  # ════════════════════════════════════════════════════════════
  # GRUPO 9 – Nanã, Omolu e cura profunda
  # ════════════════════════════════════════════════════════════
  {"name":"Avenca","sci":"Adiantum capillus-veneris","emoji":"🌿","temp":"fria","elem":"água","cat":"folha",
   "desc":"Samambaia delicada de Nanã, usada em banhos suaves de cura e proteção de crianças.",
   "spiritual":"Proteção delicada, cura e suavidade. Erva da vovó Nanã.",
   "bath_uses":["Cura suave","Proteção","Banho de crianças"],"tea_uses":[],
   "can_fumigate":False,"fumig":"","orixas":["Nanã"],
   "compat":["Alfazema","Camomila","Rosa Branca"],"incompat":[],
   "preparo":"Folhas frescas em banhos suaves. Muito delicada, não macere demais.",
   "recommended":["banho"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/8/8d/Adiantum_capillus-veneris.jpg/640px-Adiantum_capillus-veneris.jpg"},

  {"name":"Cana-do-Brejo","sci":"Costus spicatus","emoji":"🌾","temp":"fria","elem":"água","cat":"erva",
   "desc":"Planta aquática de Nanã e Iemanjá, usada em banhos de cura e limpeza energética suave.",
   "spiritual":"Limpeza suave, cura e equilíbrio das águas espirituais.",
   "bath_uses":["Limpeza suave","Cura das águas","Equilíbrio"],"tea_uses":["Diurético","Cura"],
   "can_fumigate":False,"fumig":"","orixas":["Nanã","Iemanjá"],
   "compat":["Maracujá","Alfazema","Camomila"],"incompat":[],
   "preparo":"Folhas e caule em banhos de cura. Muito usado nos rituais de Nanã.",
   "recommended":["banho","cha"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/4/48/Costus_spicatus.jpg/640px-Costus_spicatus.jpg"},

  {"name":"Quaresmeira","sci":"Tibouchina granulosa","emoji":"💜","temp":"fria","elem":"água","cat":"flor",
   "desc":"Flor roxa de Nanã usada em banhos de cura kármica e equilíbrio espiritual profundo.",
   "spiritual":"Cura kármica e equilíbrio espiritual. Erva da vovó Nanã.",
   "bath_uses":["Cura kármica","Equilíbrio espiritual"],"tea_uses":[],
   "can_fumigate":False,"fumig":"","orixas":["Nanã"],
   "compat":["Avenca","Alfazema","Cana-do-Brejo"],"incompat":[],
   "preparo":"Flores em banhos de Nanã para cura kármica.",
   "recommended":["banho"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/d/d2/Tibouchina_granulosa.jpg/640px-Tibouchina_granulosa.jpg"},

  {"name":"Zínia","sci":"Zinnia elegans","emoji":"🌸","temp":"quente","elem":"terra","cat":"flor",
   "desc":"Flor colorida de Omolu, usada em rituais de saúde, cura e proteção contra doenças.",
   "spiritual":"Cura, saúde e proteção de Obaluaê/Omolu contra doenças e epidemias.",
   "bath_uses":["Saúde","Cura","Proteção de doenças"],"tea_uses":[],
   "can_fumigate":False,"fumig":"","orixas":["Omolu"],
   "compat":["Samambaia","Espinheira-Santa","Sabugueiro"],"incompat":[],
   "preparo":"Flores em banhos de cura para enfermos ou em oferendas a Omolu.",
   "recommended":["banho"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/7/7c/Zinnia_elegans.jpg/640px-Zinnia_elegans.jpg"},

  {"name":"Sabugueiro","sci":"Sambucus nigra","emoji":"🌸","temp":"fria","elem":"água","cat":"flor",
   "desc":"Arbusto de flores brancas usado em banhos de cura, saúde e proteção de Omolu.",
   "spiritual":"Cura, proteção contra doenças e saúde espiritual.",
   "bath_uses":["Cura","Saúde","Proteção de doenças"],"tea_uses":["Gripe","Imunidade","Febre"],
   "can_fumigate":True,"fumig":"Defumação de cura para ambientes de enfermos.",
   "orixas":["Omolu","Nanã"],"compat":["Camomila","Alfazema","Erva-Cidreira"],
   "incompat":[],"preparo":"Flores em banho e chá. Seguro para uso regular.",
   "recommended":["banho","cha"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/5/5a/Sambucus_nigra_003.jpg/640px-Sambucus_nigra_003.jpg"},

  {"name":"Velame","sci":"Croton campestris","emoji":"🌿","temp":"quente","elem":"fogo","cat":"folha",
   "desc":"Erva de Omolu para purificação intensa do campo áurico e cura de energias doentias.",
   "spiritual":"Purificação intensa do campo áurico e cura de energias doentias.",
   "bath_uses":["Purificação intensa","Saúde espiritual","Cura"],"tea_uses":[],
   "can_fumigate":True,"fumig":"Defumação de purificação intensa para ambientes.",
   "orixas":["Omolu"],"compat":["Mamona","Sabugueiro","Espinheira-Santa"],
   "incompat":[],"preparo":"Folhas em banho forte de purificação. Use moderadamente.",
   "recommended":["banho","defumacao"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/a/aa/Croton_campestris.jpg/640px-Croton_campestris.jpg"},

  {"name":"Assa-Peixe","sci":"Vernonia polyanthes","emoji":"🌿","temp":"quente","elem":"fogo","cat":"folha",
   "desc":"Erva de cura de Omolu e Oxóssi para banhos de saúde e purificação das vias respiratórias.",
   "spiritual":"Cura do corpo e do espírito. Proteção de Omolu contra doenças.",
   "bath_uses":["Cura","Saúde","Purificação das vias"],"tea_uses":["Tosse","Bronquite","Gripe"],
   "can_fumigate":True,"fumig":"Defumação de cura para enfermos e ambientes de saúde.",
   "orixas":["Omolu","Oxóssi","Nanã"],"compat":["Sabugueiro","Eucalipto","Espinheira-Santa"],
   "incompat":[],"preparo":"Folhas em chá para doenças respiratórias ou banho de cura.",
   "recommended":["banho","cha","defumacao"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/0/0e/Vernonia_polyanthes.jpg/640px-Vernonia_polyanthes.jpg"},

  {"name":"Barbatimão","sci":"Stryphnodendron adstringens","emoji":"🌳","temp":"quente","elem":"terra","cat":"casca",
   "desc":"Casca sagrada de Oxumarê para limpeza profunda e regeneração espiritual.",
   "spiritual":"Limpeza profunda, cura e regeneração espiritual. Ligada a Oxumarê.",
   "bath_uses":["Limpeza profunda","Cura","Regeneração"],"tea_uses":["Cicatrização","Cura"],
   "can_fumigate":False,"fumig":"","orixas":["Oxumarê","Omolu"],
   "compat":["Copaíba","Espinheira-Santa"],"incompat":[],
   "preparo":"Casca em banho. Pode manchar roupas pela adstringência.",
   "recommended":["banho"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/3/34/Barbatimao_casca.jpg/640px-Barbatimao_casca.jpg"},

  # ════════════════════════════════════════════════════════════
  # GRUPO 10 – Iemanjá e as águas sagradas
  # ════════════════════════════════════════════════════════════
  {"name":"Camélia","sci":"Camellia japonica","emoji":"🌸","temp":"fria","elem":"água","cat":"flor",
   "desc":"Flor delicada de Iemanjá, usada em banhos de amor, paz e beleza interior.",
   "spiritual":"Amor, paz, beleza interior e conexão com as águas de Iemanjá.",
   "bath_uses":["Amor","Paz","Beleza interior"],"tea_uses":["Antioxidante","Cura"],
   "can_fumigate":False,"fumig":"","orixas":["Iemanjá"],
   "compat":["Jasmim","Alfazema","Rosa Branca","Camomila"],"incompat":[],
   "preparo":"Flores frescas em banhos de amor de Iemanjá.",
   "recommended":["banho","cha"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/4/41/Camellia_japonica_cv_extravaganza.jpg/640px-Camellia_japonica_cv_extravaganza.jpg"},

  {"name":"Algas Marinhas","sci":"Sargassum sp.","emoji":"🌊","temp":"fria","elem":"água","cat":"erva",
   "desc":"Planta do mar de Iemanjá usada em banhos de purificação das águas e conexão com o oceano.",
   "spiritual":"Purificação pelas águas do oceano e conexão profunda com Iemanjá.",
   "bath_uses":["Purificação das águas","Conexão com Iemanjá","Renovação oceânica"],"tea_uses":[],
   "can_fumigate":False,"fumig":"","orixas":["Iemanjá"],
   "compat":["Jasmim","Alfazema","Rosa Branca","Camomila"],"incompat":[],
   "preparo":"Use em banhos de Iemanjá. Pode ser fresca ou seca. Use às segundas-feiras.",
   "recommended":["banho"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/d/d2/Sargassum_wightii.jpg/640px-Sargassum_wightii.jpg"},

  {"name":"Folha-da-Costa","sci":"Kalanchoe pinnata","emoji":"🌿","temp":"fria","elem":"água","cat":"folha",
   "desc":"Folha suculenta de cura usada em banhos de Iemanjá, Oxum e Nanã para proteção e saúde.",
   "spiritual":"Cura, proteção maternal e saúde espiritual. Erva das águas sagradas.",
   "bath_uses":["Cura","Proteção maternal","Saúde","Equilíbrio"],"tea_uses":["Cura","Anti-inflamatório"],
   "can_fumigate":False,"fumig":"","orixas":["Iemanjá","Oxum","Nanã"],
   "compat":["Alfazema","Camomila","Rosa Branca"],"incompat":[],
   "preparo":"Folhas suculentas em banhos de cura. Pode ser usada fresca amassada.",
   "recommended":["banho"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/b/b5/Kalanchoe_pinnata_ies.jpg/640px-Kalanchoe_pinnata_ies.jpg"},

  {"name":"Pata-de-Vaca","sci":"Bauhinia forficata","emoji":"🌿","temp":"fria","elem":"água","cat":"folha",
   "desc":"Folha medicinal de Oxum para saúde, equilíbrio hormonal e cura espiritual feminina.",
   "spiritual":"Equilíbrio, saúde e proteção de Oxum. Cura das doenças femininas.",
   "bath_uses":["Saúde","Equilíbrio","Cura feminina"],"tea_uses":["Diabetes","Diurético","Saúde"],
   "can_fumigate":False,"fumig":"","orixas":["Oxum"],
   "compat":["Colônia","Alfazema","Erva-Cidreira"],"incompat":[],
   "preparo":"Folhas em chá para saúde. Em banho para equilíbrio feminino.",
   "recommended":["banho","cha"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/6/60/Bauhinia_forficata.jpg/640px-Bauhinia_forficata.jpg"},

  {"name":"Orquídea Branca","sci":"Orchidaceae (branca)","emoji":"🤍","temp":"fria","elem":"água","cat":"flor",
   "desc":"Flor rara de elevação espiritual, clareza mediúnica e conexão com guias de luz.",
   "spiritual":"Clareza mediúnica, refinamento espiritual e conexão com guias elevados.",
   "bath_uses":["Clareza mediúnica","Refinamento espiritual"],"tea_uses":[],
   "can_fumigate":False,"fumig":"","orixas":["Oxalá","Iemanjá"],
   "compat":["Jasmim","Alfazema","Rosa Branca"],"incompat":[],
   "preparo":"Flores frescas em banhos de limpeza suave e refinamento.",
   "recommended":["banho"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/4/4c/White_orchid.jpg/640px-White_orchid.jpg"},

  # ════════════════════════════════════════════════════════════
  # GRUPO 11 – Prosperidade, sorte e negócios
  # ════════════════════════════════════════════════════════════
  {"name":"Anis Estrelado","sci":"Illicium verum","emoji":"⭐","temp":"quente","elem":"fogo","cat":"fruto",
   "desc":"Fruto aromático de sorte, atração espiritual e abertura de caminhos em negócios.",
   "spiritual":"Abertura de portas, proteção profunda e desenvolvimento mediúnico.",
   "bath_uses":["Sorte","Proteção","Abertura de caminhos"],"tea_uses":["Calma","Equilíbrio","Digestão"],
   "can_fumigate":True,"fumig":"Defumação de sorte e abertura com aroma doce.",
   "orixas":["Oxóssi","Oxum"],"compat":["Canela","Cravo","Manjericão"],
   "incompat":[],"preparo":"Fruto inteiro em banhos e defumações.",
   "recommended":["banho","cha","defumacao"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/2/2a/Illicium_verum_fruit.jpg/640px-Illicium_verum_fruit.jpg"},

  {"name":"Noz-Moscada","sci":"Myristica fragrans","emoji":"🫙","temp":"quente","elem":"fogo","cat":"semente",
   "desc":"Semente aromática de prosperidade, sorte e atração usada em defumações de negócios.",
   "spiritual":"Atração de sorte, prosperidade e proteção nos negócios.",
   "bath_uses":["Sorte","Prosperidade"],"tea_uses":["Tempero","Digestão"],
   "can_fumigate":True,"fumig":"Defumação de prosperidade e atração de sorte para negócios.",
   "orixas":["Xangô","Oxum"],"compat":["Canela","Cravo","Louro"],
   "incompat":[],"preparo":"Use ralada em defumações. Em excesso pode ser tóxica.",
   "recommended":["defumacao"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/8/8f/Nutmeg_2.jpg/640px-Nutmeg_2.jpg"},

  {"name":"Urucum","sci":"Bixa orellana","emoji":"🔴","temp":"quente","elem":"fogo","cat":"semente",
   "desc":"Semente vermelha sagrada de Xangô e Oxóssi, usada para proteção e consagração de rituais.",
   "spiritual":"Proteção, força e consagração. A tinta vermelha é sinal de proteção sagrada.",
   "bath_uses":["Proteção","Consagração","Força"],"tea_uses":[],
   "can_fumigate":False,"fumig":"","orixas":["Xangô","Oxóssi"],
   "compat":["Peregum","Louro","Arruda"],"incompat":[],
   "preparo":"Sementes em banho de consagração. Tinge a pele — use com cuidado.",
   "recommended":["banho"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/c/c5/Bixa_orellana.jpg/640px-Bixa_orellana.jpg"},

  {"name":"Imburana","sci":"Commiphora leptophloeos","emoji":"🌳","temp":"quente","elem":"fogo","cat":"semente",
   "desc":"Semente e árvore sagrada do sertão para cura emocional, ânimo e força espiritual.",
   "spiritual":"Cura emocional, força e ânimo espiritual nas adversidades da vida.",
   "bath_uses":["Cura emocional","Ânimo","Força"],"tea_uses":["Ânimo","Cura"],
   "can_fumigate":True,"fumig":"Defumação para cura emocional e ânimo.",
   "orixas":["Oxóssi","Omolu"],"compat":["Alecrim","Canela","Anis Estrelado"],
   "incompat":[],"preparo":"Sementes em defumação ou banho de cura emocional.",
   "recommended":["banho","cha","defumacao"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/8/82/Commiphora_leptophloeos.jpg/640px-Commiphora_leptophloeos.jpg"},

  # ════════════════════════════════════════════════════════════
  # GRUPO 12 – Oxumarê e transformação
  # ════════════════════════════════════════════════════════════
  {"name":"Graviola","sci":"Annona muricata","emoji":"🌿","temp":"fria","elem":"água","cat":"folha",
   "desc":"Folha de Oxumarê para equilíbrio, cura e harmonia com as mudanças da vida.",
   "spiritual":"Equilíbrio nas mudanças, adaptabilidade e harmonia. Ligada a Oxumarê.",
   "bath_uses":["Equilíbrio","Harmonia","Adaptabilidade"],"tea_uses":["Imunidade","Cura","Relaxamento"],
   "can_fumigate":False,"fumig":"","orixas":["Oxumarê"],
   "compat":["Alfazema","Erva-Cidreira","Maracujá"],"incompat":[],
   "preparo":"Folhas em chá ou banho. Usar com moderação interna.",
   "recommended":["banho","cha"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/4/42/Annona_muricata.jpg/640px-Annona_muricata.jpg"},

  {"name":"Poejo","sci":"Mentha pulegium","emoji":"🌿","temp":"quente","elem":"ar","cat":"erva",
   "desc":"Erva aromática de Oxumarê para equilíbrio e harmonia com os ciclos da vida.",
   "spiritual":"Renovação, equilíbrio e harmonia com os ciclos da vida.",
   "bath_uses":["Renovação","Equilíbrio","Harmonia"],"tea_uses":["Digestão","Gripe"],
   "can_fumigate":True,"fumig":"Defumação de renovação e equilíbrio dos ciclos.",
   "orixas":["Oxumarê"],"compat":["Hortelã","Capim-Limão","Erva-Cidreira"],
   "incompat":[],"preparo":"Contraindicado em gestantes e crianças pequenas.",
   "recommended":["banho","defumacao"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/e/e8/Mentha_pulegium_-_K%C3%B6hler%E2%80%93s_Medizinal-Pflanzen-120.jpg/640px-Mentha_pulegium_-_K%C3%B6hler%E2%80%93s_Medizinal-Pflanzen-120.jpg"},

  # ════════════════════════════════════════════════════════════
  # GRUPO 13 – Ervas medicinais-espirituais complementares
  # ════════════════════════════════════════════════════════════
  {"name":"Erva-de-São-João","sci":"Hypericum perforatum","emoji":"🌼","temp":"quente","elem":"fogo","cat":"flor",
   "desc":"Flor solar de cura emocional e proteção contra melancolia e depressão espiritual.",
   "spiritual":"Cura emocional, proteção contra obsessão melancólica e luz na escuridão.",
   "bath_uses":["Cura emocional","Proteção","Luz espiritual"],"tea_uses":["Depressão leve","Equilíbrio","Cura"],
   "can_fumigate":True,"fumig":"Defumação de luz espiritual e cura emocional.",
   "orixas":["Oxalá","Xangô"],"compat":["Alfazema","Camomila","Alecrim"],
   "incompat":[],"preparo":"Flores e folhas em chá e banho. Pode causar fotossensibilidade.",
   "recommended":["banho","cha","defumacao"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/6/6b/Hypericum_perforatum_a1.jpg/640px-Hypericum_perforatum_a1.jpg"},

  {"name":"Tomilho","sci":"Thymus vulgaris","emoji":"🌿","temp":"quente","elem":"fogo","cat":"erva",
   "desc":"Erva poderosa de purificação, proteção e saúde espiritual da tradição mediterrânea.",
   "spiritual":"Purificação, coragem e proteção. Fortalece o campo áurico.",
   "bath_uses":["Purificação","Proteção","Saúde"],"tea_uses":["Imunidade","Gripe","Antisséptico"],
   "can_fumigate":True,"fumig":"Defumação de purificação e proteção.",
   "orixas":["Ogum","Oxalá"],"compat":["Alecrim","Sálvia","Louro"],
   "incompat":[],"preparo":"Fresco ou seco. Uma das melhores ervas para gripe.",
   "recommended":["banho","cha","defumacao"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/2/2e/Thymus_vulgaris_%28Thymian%29_IMG_7722.JPG/640px-Thymus_vulgaris_%28Thymian%29_IMG_7722.JPG"},

  {"name":"Manjerona","sci":"Origanum majorana","emoji":"🌿","temp":"morna","elem":"ar","cat":"erva",
   "desc":"Erva suave de paz, amor e harmonia. Complemento de rituais de Oxalá e Omolu.",
   "spiritual":"Paz, amor e harmonia suave no ambiente espiritual.",
   "bath_uses":["Paz","Harmonia","Amor suave"],"tea_uses":["Calma","Digestão"],
   "can_fumigate":True,"fumig":"Defumação suave de paz e harmonia para casas.",
   "orixas":["Oxalá","Omolu"],"compat":["Alfazema","Camomila","Erva-Cidreira"],
   "incompat":[],"preparo":"Fresca ou seca em chá e banho. Muito versátil.",
   "recommended":["banho","cha","defumacao"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/7/74/Origanum_majorana_-_K%C3%B6hler%E2%80%93s_Medizinal-Pflanzen-115.jpg/640px-Origanum_majorana_-_K%C3%B6hler%E2%80%93s_Medizinal-Pflanzen-115.jpg"},

  {"name":"Malva","sci":"Malva sylvestris","emoji":"💜","temp":"fria","elem":"água","cat":"flor",
   "desc":"Flor de Oxalá e Iemanjá para suavização, cura e equilíbrio energético.",
   "spiritual":"Suavização, equilíbrio e cura suave do campo espiritual.",
   "bath_uses":["Suavização","Equilíbrio","Cura suave"],"tea_uses":["Anti-inflamatório","Garganta","Cura"],
   "can_fumigate":False,"fumig":"","orixas":["Oxalá","Iemanjá"],
   "compat":["Alfazema","Camomila","Erva-Cidreira"],"incompat":[],
   "preparo":"Flores e folhas em chá para cura ou banho suave.",
   "recommended":["banho","cha"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/8/83/Malva_sylvestris_-_K%C3%B6hler%E2%80%93s_Medizinal-Pflanzen-190.jpg/640px-Malva_sylvestris_-_K%C3%B6hler%E2%80%93s_Medizinal-Pflanzen-190.jpg"},

  {"name":"Erva-de-Santa-Luzia","sci":"Commelina benghalensis","emoji":"🌿","temp":"fria","elem":"água","cat":"erva",
   "desc":"Erva de Oxalá e Oxum para cura da visão espiritual e desenvolvimento mediúnico.",
   "spiritual":"Clareza mediúnica, desenvolvimento espiritual e cura da visão espiritual.",
   "bath_uses":["Clareza mediúnica","Desenvolvimento espiritual","Cura da visão"],"tea_uses":["Cura dos olhos"],
   "can_fumigate":False,"fumig":"","orixas":["Oxalá","Oxum"],
   "compat":["Alfazema","Verbena","Camomila"],"incompat":[],
   "preparo":"Folhas em banho de desenvolvimento mediúnico.",
   "recommended":["banho"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/f/fc/Commelina_benghalensis.jpg/640px-Commelina_benghalensis.jpg"},

  {"name":"Capeba","sci":"Pothomorphe umbellata","emoji":"🌿","temp":"fria","elem":"água","cat":"folha",
   "desc":"Folha de Iansã e Nanã para descarrego suave, limpeza e equilíbrio.",
   "spiritual":"Limpeza suave, descarrego e equilíbrio das energias femininas.",
   "bath_uses":["Descarrego suave","Limpeza","Equilíbrio"],"tea_uses":["Anti-inflamatório","Cura"],
   "can_fumigate":False,"fumig":"","orixas":["Iansã","Nanã"],
   "compat":["Alfazema","Erva-Cidreira","Vassourinha"],"incompat":[],
   "preparo":"Folhas em banho de descarrego suave ou chá terapêutico.",
   "recommended":["banho"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/a/a5/Pothomorphe_umbellata.jpg/640px-Pothomorphe_umbellata.jpg"},

  {"name":"Barba-de-Velho","sci":"Tillandsia usneoides","emoji":"🌿","temp":"fria","elem":"ar","cat":"folha",
   "desc":"Planta aérea de Xangô e Omolu para descarrego de energias antigas e ancestrais.",
   "spiritual":"Descarrego de energias antigas, ancestralidade e equilíbrio kármico.",
   "bath_uses":["Descarrego de energias ancestrais","Equilíbrio kármico"],"tea_uses":[],
   "can_fumigate":True,"fumig":"Defumação para descarrego de heranças kármicas pesadas.",
   "orixas":["Xangô","Omolu"],"compat":["Cipó-Mil-Homens","Losna","Arruda"],
   "incompat":[],"preparo":"Planta aérea em banho de descarrego. Não ingira.",
   "recommended":["banho","defumacao"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/4/44/Tillandsia_usneoides0.jpg/640px-Tillandsia_usneoides0.jpg"},

  {"name":"Sete-Sangrias","sci":"Cuphea carthagenensis","emoji":"🌿","temp":"quente","elem":"fogo","cat":"erva",
   "desc":"Erva de Omolu para cura de doenças de pele e purificação do sangue espiritual.",
   "spiritual":"Purificação do sangue espiritual e cura da pele sutil.",
   "bath_uses":["Purificação do sangue","Cura da pele","Saúde"],"tea_uses":["Pressão","Circulação"],
   "can_fumigate":False,"fumig":"","orixas":["Omolu"],
   "compat":["Velame","Assa-Peixe","Copaíba"],"incompat":[],
   "preparo":"Folhas e flores em banho de cura. Chá para circulação com moderação.",
   "recommended":["banho","cha"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/5/54/Cuphea_carthagenensis.jpg/640px-Cuphea_carthagenensis.jpg"},

  {"name":"Fedegoso","sci":"Senna obtusifolia","emoji":"🌿","temp":"quente","elem":"fogo","cat":"erva",
   "desc":"Erva de Xangô para justiça espiritual, proteção e limpeza de espaços.",
   "spiritual":"Justiça espiritual, proteção e limpeza de espaços desequilibrados.",
   "bath_uses":["Justiça","Proteção","Limpeza de espaços"],"tea_uses":[],
   "can_fumigate":True,"fumig":"Defumação de justiça para ambientes com conflitos.",
   "orixas":["Xangô"],"compat":["Louro","Aroeira","Arruda"],
   "incompat":[],"preparo":"Folhas em banho de justiça. Contraindicado em gestantes.",
   "recommended":["banho","defumacao"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/b/b4/Senna_obtusifolia.jpg/640px-Senna_obtusifolia.jpg"},

  {"name":"Aloe Vera","sci":"Aloe barbadensis miller","emoji":"🌵","temp":"fria","elem":"água","cat":"folha",
   "desc":"Planta de cura universal usada na umbanda para saúde, renovação energética e proteção.",
   "spiritual":"Renovação, cura e proteção suave do campo áurico.",
   "bath_uses":["Renovação","Cura","Proteção suave"],"tea_uses":[],
   "can_fumigate":False,"fumig":"","orixas":["Oxalá","Omolu"],
   "compat":["Alfazema","Camomila"],"incompat":[],
   "preparo":"Gel das folhas em banhos de cura. Não ingira sem orientação.",
   "recommended":["banho"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/4/4b/Aloe_vera_flower_inset.png/640px-Aloe_vera_flower_inset.png"},

  {"name":"Erva-de-Santa-Maria","sci":"Chenopodium ambrosioides","emoji":"🌿","temp":"quente","elem":"fogo","cat":"erva",
   "desc":"Erva de Oxum e Oxalá para purificação e limpeza de parasitas espirituais.",
   "spiritual":"Limpeza de parasitas espirituais, purificação e proteção.",
   "bath_uses":["Purificação","Limpeza de parasitas","Proteção"],"tea_uses":["Antiparasitário","Digestão"],
   "can_fumigate":True,"fumig":"Defumação para limpar parasitas espirituais.",
   "orixas":["Oxum","Oxalá"],"compat":["Alecrim","Sálvia","Arruda"],
   "incompat":[],"preparo":"Contraindicada em gestantes. Em chá, somente com orientação.",
   "recommended":["banho","defumacao"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/7/74/Chenopodium_ambrosioides_kz01.jpg/640px-Chenopodium_ambrosioides_kz01.jpg"},
  # ════════════════════════════════════════════════════════════
  # GRUPO 14 – Mais ervas de proteção e rituais
  # ════════════════════════════════════════════════════════════
  {"name":"Guiné-Pimenta","sci":"Xylopia aethiopica","emoji":"🌿","temp":"quente","elem":"fogo","cat":"fruto",
   "desc":"Fruto da floresta africana de forte proteção espiritual e abertura de caminhos ancestrais.",
   "spiritual":"Proteção forte, abertura de caminhos e força ancestral africana.",
   "bath_uses":["Proteção","Abertura de caminhos","Força ancestral"],"tea_uses":[],
   "can_fumigate":True,"fumig":"Defumação de proteção e abertura de caminhos ancestrais.",
   "orixas":["Exu","Ogum"],"compat":["Arruda","Guiné","Pimenta-da-Guiné"],
   "incompat":[],"preparo":"Use com moderação. Sementes em banho de força.",
   "recommended":["banho","defumacao"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/f/fb/Xylopia_aethiopica_fruits.jpg/640px-Xylopia_aethiopica_fruits.jpg"},

  {"name":"Arnica","sci":"Arnica montana","emoji":"🌼","temp":"quente","elem":"fogo","cat":"flor",
   "desc":"Flor de cura de Ogum, usada para curar feridas físicas e espirituais após batalhas.",
   "spiritual":"Cura de feridas espirituais e proteção após batalhas energéticas intensas.",
   "bath_uses":["Cura","Proteção pós-batalha"],"tea_uses":[],
   "can_fumigate":False,"fumig":"","orixas":["Ogum","Omolu"],
   "compat":["Espinheira-Santa","Copaíba"],"incompat":[],
   "preparo":"Apenas uso externo — tóxica se ingerida. Banho de cura pós-batalha espiritual.",
   "recommended":["banho"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/4/49/Arnica_montana_-_K%C3%B6hler%E2%80%93s_Medizinal-Pflanzen-016.jpg/640px-Arnica_montana_-_K%C3%B6hler%E2%80%93s_Medizinal-Pflanzen-016.jpg"},

  {"name":"Alevante","sci":"Mentha spicata","emoji":"🌿","temp":"fria","elem":"ar","cat":"erva",
   "desc":"Hortelã suave de Oxalá usada em banhos de manutenção, frescor e clareza mental.",
   "spiritual":"Frescor, clareza e limpeza suave do campo áurico.",
   "bath_uses":["Frescor","Clareza","Manutenção energética"],"tea_uses":["Digestão","Calma","Frescura"],
   "can_fumigate":True,"fumig":"Defumação leve de frescor e clareza.",
   "orixas":["Oxalá","Iemanjá"],"compat":["Hortelã","Capim-Limão","Erva-Cidreira"],
   "incompat":[],"preparo":"Fresca ou seca em chás e banhos diários. Muito segura.",
   "recommended":["banho","cha","defumacao"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/9/9e/Mentha_spicata_-_K%C3%B6hler%E2%80%93s_Medizinal-Pflanzen-118.jpg/640px-Mentha_spicata_-_K%C3%B6hler%E2%80%93s_Medizinal-Pflanzen-118.jpg"},

  {"name":"Orégano","sci":"Origanum vulgare","emoji":"🌿","temp":"quente","elem":"fogo","cat":"erva",
   "desc":"Erva solar de proteção, saúde e prosperidade usada em banhos e defumações.",
   "spiritual":"Proteção do lar, saúde e atração de prosperidade.",
   "bath_uses":["Proteção","Saúde","Prosperidade"],"tea_uses":["Digestão","Imunidade","Tosse"],
   "can_fumigate":True,"fumig":"Defumação de proteção e saúde para o lar.",
   "orixas":["Ogum","Oxalá"],"compat":["Alecrim","Sálvia","Tomilho"],
   "incompat":[],"preparo":"Fresco ou seco. Muito versátil em cozinha e rituais.",
   "recommended":["banho","cha","defumacao"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/d/d2/Origanum_vulgare_-_K%C3%B6hler%E2%80%93s_Medizinal-Pflanzen-107.jpg/640px-Origanum_vulgare_-_K%C3%B6hler%E2%80%93s_Medizinal-Pflanzen-107.jpg"},

  {"name":"Calumba","sci":"Jatrorrhiza palmata","emoji":"🌿","temp":"quente","elem":"terra","cat":"raiz",
   "desc":"Raiz amarga africana de proteção espiritual e abertura de caminhos bloqueados.",
   "spiritual":"Proteção ancestral africana e desobstrução de caminhos.",
   "bath_uses":["Proteção","Abertura de caminhos"],"tea_uses":[],
   "can_fumigate":True,"fumig":"Defumação de proteção ancestral.",
   "orixas":["Exu","Ogum"],"compat":["Guiné","Arruda","Pimenta-da-Guiné"],
   "incompat":[],"preparo":"Raiz seca em banho ou defumação.",
   "recommended":["banho","defumacao"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/5/5c/Jatrorrhiza_palmata_-_K%C3%B6hler%E2%80%93s_Medizinal-Pflanzen-088.jpg/640px-Jatrorrhiza_palmata_-_K%C3%B6hler%E2%80%93s_Medizinal-Pflanzen-088.jpg"},

  {"name":"Picão","sci":"Bidens pilosa","emoji":"🌿","temp":"quente","elem":"terra","cat":"erva",
   "desc":"Erva medicinal de Omolu usada para cura, saúde e descarrego suave.",
   "spiritual":"Cura, saúde e proteção suave de Omolu e Oxóssi.",
   "bath_uses":["Cura","Saúde","Descarrego suave"],"tea_uses":["Anti-inflamatório","Imunidade","Cura"],
   "can_fumigate":False,"fumig":"","orixas":["Omolu","Oxóssi"],
   "compat":["Espinheira-Santa","Boldo","Assa-Peixe"],"incompat":[],
   "preparo":"Planta inteira em chá ou banho de cura. Muito comum e acessível.",
   "recommended":["banho","cha"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/Bidens_pilosa.jpg/640px-Bidens_pilosa.jpg"},

  {"name":"Erva-Tostão","sci":"Boerhavia diffusa","emoji":"🌿","temp":"fria","elem":"água","cat":"erva",
   "desc":"Erva de Iemanjá e Oxum para cura dos rins, equilíbrio hídrico e limpeza espiritual.",
   "spiritual":"Limpeza das águas corporais e espirituais. Equilíbrio energético fluido.",
   "bath_uses":["Limpeza das águas","Equilíbrio","Cura"],"tea_uses":["Rins","Diurético","Cura"],
   "can_fumigate":False,"fumig":"","orixas":["Iemanjá","Oxum"],
   "compat":["Cana-do-Brejo","Alfazema","Camomila"],"incompat":[],
   "preparo":"Raiz e folhas em chá diurético ou banho de limpeza.",
   "recommended":["banho","cha"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/5/5c/Boerhavia_diffusa.jpg/640px-Boerhavia_diffusa.jpg"},

  {"name":"Gervão","sci":"Stachytarpheta cayennensis","emoji":"🌿","temp":"quente","elem":"fogo","cat":"erva",
   "desc":"Erva de Xangô usada em banhos de justiça, limpeza e corte de laços negativos.",
   "spiritual":"Justiça espiritual, corte de laços e proteção contra demandas.",
   "bath_uses":["Justiça","Corte de laços","Limpeza"],"tea_uses":["Febre","Digestão"],
   "can_fumigate":True,"fumig":"Defumação de justiça e corte de demandas.",
   "orixas":["Xangô"],"compat":["Carqueja","Aroeira","Alecrim"],
   "incompat":[],"preparo":"Folhas em banho de justiça. Contraindicado em gestantes.",
   "recommended":["banho","defumacao"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/1/1b/Stachytarpheta_cayennensis_2.jpg/640px-Stachytarpheta_cayennensis_2.jpg"},

  {"name":"Jurubeba","sci":"Solanum paniculatum","emoji":"🌿","temp":"quente","elem":"fogo","cat":"folha",
   "desc":"Planta de Xangô e Ogum para purificação do fígado espiritual e coragem.",
   "spiritual":"Purificação interna, coragem e força de Xangô e Ogum.",
   "bath_uses":["Purificação","Coragem","Força"],"tea_uses":["Fígado","Digestão","Amargura"],
   "can_fumigate":False,"fumig":"","orixas":["Xangô","Ogum"],
   "compat":["Carqueja","Boldo","Alecrim"],"incompat":[],
   "preparo":"Frutos e folhas em chá ou banho de purificação.",
   "recommended":["banho","cha"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/4/45/Solanum_paniculatum.jpg/640px-Solanum_paniculatum.jpg"},

  {"name":"Pariparoba","sci":"Piper umbellatum","emoji":"🌿","temp":"quente","elem":"terra","cat":"folha",
   "desc":"Folha de Omolu usada em banhos de cura da pele espiritual e proteção de enfermos.",
   "spiritual":"Cura da pele sutil, proteção de enfermos e força de Omolu.",
   "bath_uses":["Cura da pele","Proteção de enfermos","Saúde"],"tea_uses":["Anti-inflamatório"],
   "can_fumigate":True,"fumig":"Defumação de cura para enfermos.",
   "orixas":["Omolu"],"compat":["Velame","Sete-Sangrias","Assa-Peixe"],
   "incompat":[],"preparo":"Folhas em banho de cura ou defumação medicinal.",
   "recommended":["banho","defumacao"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/8/8c/Piper_umbellatum.jpg/640px-Piper_umbellatum.jpg"},

  # ════════════════════════════════════════════════════════════
  # GRUPO 15 – Ervas de Ogum e guerreiros
  # ════════════════════════════════════════════════════════════
  {"name":"Espinheiro","sci":"Gleditsia triacanthos","emoji":"🌳","temp":"quente","elem":"fogo","cat":"casca",
   "desc":"Árvore de espinhos de Ogum, usada para proteção física e espiritual de guerreiros.",
   "spiritual":"Proteção guerreira, criação de barreiras espirituais e corte de demandas.",
   "bath_uses":["Proteção guerreira","Barreiras espirituais"],"tea_uses":[],
   "can_fumigate":True,"fumig":"Defumação de proteção guerreira para lares e terreiros.",
   "orixas":["Ogum"],"compat":["Arruda","Guiné","Alecrim"],
   "incompat":[],"preparo":"Cascas em banho de proteção. Use do pescoço para baixo.",
   "recommended":["banho","defumacao"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/d/d7/Gleditsia_triacanthos.jpg/640px-Gleditsia_triacanthos.jpg"},

  {"name":"Bambu","sci":"Bambusa vulgaris","emoji":"🎋","temp":"neutra","elem":"terra","cat":"folha",
   "desc":"Planta de força, flexibilidade e crescimento espiritual. Ligada a Oxóssi e Ogum.",
   "spiritual":"Crescimento, flexibilidade espiritual e força na adversidade.",
   "bath_uses":["Força","Crescimento","Flexibilidade"],"tea_uses":["Mineralização","Saúde"],
   "can_fumigate":False,"fumig":"","orixas":["Ogum","Oxóssi"],
   "compat":["Samambaia","Louro","Alecrim"],"incompat":[],
   "preparo":"Folhas em banho de crescimento e força. Planta de manutenção do lar.",
   "recommended":["banho","cha"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/b/b1/Bamboo_Forest.jpg/640px-Bamboo_Forest.jpg"},

  {"name":"Mostarda Preta","sci":"Brassica nigra","emoji":"🌿","temp":"quente","elem":"fogo","cat":"semente",
   "desc":"Semente de Exu e Ogum para proteção, afastamento de mal e abertura de caminhos.",
   "spiritual":"Proteção contra o mal, afastamento de inimigos e força espiritual.",
   "bath_uses":["Proteção","Afastar mal","Força"],"tea_uses":[],
   "can_fumigate":True,"fumig":"Defumação de proteção e afastamento do mal.",
   "orixas":["Exu","Ogum"],"compat":["Arruda","Guiné","Alecrim"],
   "incompat":[],"preparo":"Sementes em banho ou defumação de proteção.",
   "recommended":["banho","defumacao"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/c/c4/Mustard-45328_1920.jpg/640px-Mustard-45328_1920.jpg"},

  {"name":"Carmo","sci":"Alpinia speciosa","emoji":"🌺","temp":"quente","elem":"fogo","cat":"folha",
   "desc":"Folha de Ogum e Iansã para força, proteção e abertura de caminhos difíceis.",
   "spiritual":"Força, abertura de caminhos e proteção guerreira.",
   "bath_uses":["Força","Abertura de caminhos","Proteção"],"tea_uses":[],
   "can_fumigate":True,"fumig":"Defumação de força e abertura de caminhos.",
   "orixas":["Ogum","Iansã"],"compat":["Louro","Alecrim","Arruda"],
   "incompat":[],"preparo":"Folhas frescas em banhos de força e abertura.",
   "recommended":["banho","defumacao"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/5/53/Alpinia_zerumbet_%28Shell_ginger%29.jpg/640px-Alpinia_zerumbet_%28Shell_ginger%29.jpg"},

  # ════════════════════════════════════════════════════════════
  # GRUPO 16 – Flores e plantas especiais
  # ════════════════════════════════════════════════════════════
  {"name":"Violeta","sci":"Viola odorata","emoji":"💜","temp":"fria","elem":"água","cat":"flor",
   "desc":"Flor delicada de Iemanjá e Oxum para paz, amor e suavização de conflitos.",
   "spiritual":"Paz interior, amor incondicional e suavização de relações tensas.",
   "bath_uses":["Paz","Amor","Suavização de conflitos"],"tea_uses":["Cura","Calma"],
   "can_fumigate":False,"fumig":"","orixas":["Iemanjá","Oxum"],
   "compat":["Jasmim","Alfazema","Camomila","Rosa Branca"],"incompat":[],
   "preparo":"Flores frescas em banhos de paz e suavização.",
   "recommended":["banho","cha"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/e/ef/Viola_odorata_fg01.jpg/640px-Viola_odorata_fg01.jpg"},

  {"name":"Lavanda-do-Mar","sci":"Limonium sinuatum","emoji":"💜","temp":"fria","elem":"água","cat":"flor",
   "desc":"Flor seca de Iemanjá usada em rituais de cura, paz e conexão com o oceano.",
   "spiritual":"Conexão com as águas, paz e cura suave de Iemanjá.",
   "bath_uses":["Paz","Conexão com águas","Cura suave"],"tea_uses":[],
   "can_fumigate":True,"fumig":"Defumação de paz e cura associada às águas do mar.",
   "orixas":["Iemanjá"],"compat":["Algas Marinhas","Alfazema","Jasmim"],
   "incompat":[],"preparo":"Flores secas em banhos ou defumações de Iemanjá.",
   "recommended":["banho","defumacao"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/9/96/Limonium_sinuatum.jpg/640px-Limonium_sinuatum.jpg"},

  {"name":"Tulipa","sci":"Tulipa sp.","emoji":"🌷","temp":"fria","elem":"água","cat":"flor",
   "desc":"Flor elegante de Oxum e Iemanjá para amor, beleza e elevação espiritual.",
   "spiritual":"Beleza interior, amor e elevação das vibrações.",
   "bath_uses":["Amor","Beleza","Elevação"],"tea_uses":[],
   "can_fumigate":False,"fumig":"","orixas":["Oxum","Iemanjá"],
   "compat":["Rosa Vermelha","Jasmim","Colônia"],"incompat":[],
   "preparo":"Pétalas frescas em banhos de amor e beleza espiritual.",
   "recommended":["banho"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/4/41/Tulipa_suaveolens_floriade2005.jpg/640px-Tulipa_suaveolens_floriade2005.jpg"},

  {"name":"Gérbera","sci":"Gerbera jamesonii","emoji":"🌸","temp":"quente","elem":"fogo","cat":"flor",
   "desc":"Flor colorida e alegre de Xangô e Oxum para alegria, vitalidade e abertura do coração.",
   "spiritual":"Alegria, vitalidade espiritual e abertura do coração para o amor.",
   "bath_uses":["Alegria","Vitalidade","Abertura do coração"],"tea_uses":[],
   "can_fumigate":False,"fumig":"","orixas":["Xangô","Oxum","Iansã"],
   "compat":["Calêndula","Girassol","Rosa Amarela"],"incompat":[],
   "preparo":"Pétalas frescas em banhos matinais de alegria e vitalidade.",
   "recommended":["banho"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/f/f3/Gerbera_jamesonii.jpg/640px-Gerbera_jamesonii.jpg"},

  {"name":"Mimo-de-Vênus","sci":"Dicentra spectabilis","emoji":"🌸","temp":"fria","elem":"água","cat":"flor",
   "desc":"Flor em forma de coração de Oxum e Iemanjá para amor, cura emocional e ternura.",
   "spiritual":"Amor, ternura e cura emocional profunda.",
   "bath_uses":["Amor","Cura emocional","Ternura"],"tea_uses":[],
   "can_fumigate":False,"fumig":"","orixas":["Oxum","Iemanjá"],
   "compat":["Rosa Vermelha","Jasmim","Violeta"],"incompat":[],
   "preparo":"Flores frescas em banhos de amor e cura emocional.",
   "recommended":["banho"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/e/e6/Bleeding_heart_ies.jpg/640px-Bleeding_heart_ies.jpg"},

  # ════════════════════════════════════════════════════════════
  # GRUPO 17 – Ervas medicinais sagradas adicionais
  # ════════════════════════════════════════════════════════════
  {"name":"Babosa-Brava","sci":"Bryophyllum calycinum","emoji":"🌵","temp":"fria","elem":"água","cat":"folha",
   "desc":"Parente da babosa usada em banhos de cura, renovação e proteção de Iemanjá.",
   "spiritual":"Renovação, cura e proteção das águas. Ligada a Iemanjá e Nanã.",
   "bath_uses":["Renovação","Cura","Proteção das águas"],"tea_uses":["Anti-inflamatório","Cura"],
   "can_fumigate":False,"fumig":"","orixas":["Iemanjá","Nanã"],
   "compat":["Alfazema","Erva-Cidreira","Aloe Vera"],"incompat":[],
   "preparo":"Folhas frescas amassadas em banho de cura e renovação.",
   "recommended":["banho"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/b/b5/Kalanchoe_pinnata_ies.jpg/640px-Kalanchoe_pinnata_ies.jpg"},

  {"name":"Cipo-de-São-João","sci":"Pyrostegia venusta","emoji":"🔶","temp":"quente","elem":"fogo","cat":"flor",
   "desc":"Flor laranja de Xangô e Iansã para alegria, força e renovação espiritual.",
   "spiritual":"Alegria, força e renovação energética do campo áurico.",
   "bath_uses":["Alegria","Força","Renovação energética"],"tea_uses":[],
   "can_fumigate":False,"fumig":"","orixas":["Xangô","Iansã"],
   "compat":["Calêndula","Girassol","Hibisco"],"incompat":[],
   "preparo":"Flores frescas em banhos de alegria e força. Muito bela visualmente.",
   "recommended":["banho"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/1/19/Pyrostegia_venusta1.jpg/640px-Pyrostegia_venusta1.jpg"},

  {"name":"Três-Marias","sci":"Bougainvillea spectabilis","emoji":"🌸","temp":"quente","elem":"fogo","cat":"flor",
   "desc":"Planta vibrante de Iansã e Xangô usada em banhos de força, beleza e proteção.",
   "spiritual":"Força feminina, beleza espiritual e proteção de Iansã.",
   "bath_uses":["Força feminina","Beleza espiritual","Proteção"],"tea_uses":["Tosse","Bronquite"],
   "can_fumigate":False,"fumig":"","orixas":["Iansã","Xangô"],
   "compat":["Hibisco","Calêndula","Rosa Vermelha"],"incompat":[],
   "preparo":"Flores em banho de força e beleza. Chá para respiração.",
   "recommended":["banho","cha"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/9/9e/Bougainvillea_spectabilis_-_Bougainville.jpg/640px-Bougainvillea_spectabilis_-_Bougainville.jpg"},

  {"name":"Transagem","sci":"Plantago major","emoji":"🌿","temp":"fria","elem":"terra","cat":"folha",
   "desc":"Erva humilde de Omolu e Oxalá para cura, humildade espiritual e equilíbrio.",
   "spiritual":"Humildade, cura e equilíbrio espiritual. A erva dos humildes e enfermos.",
   "bath_uses":["Cura","Humildade espiritual","Equilíbrio"],"tea_uses":["Garganta","Anti-inflamatório","Cura"],
   "can_fumigate":False,"fumig":"","orixas":["Omolu","Oxalá"],
   "compat":["Assa-Peixe","Espinheira-Santa","Boldo"],"incompat":[],
   "preparo":"Folhas em chá ou banho de cura. Muito acessível e segura.",
   "recommended":["banho","cha"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/9/9c/Plantago_major_-_K%C3%B6hler%E2%80%93s_Medizinal-Pflanzen-112.jpg/640px-Plantago_major_-_K%C3%B6hler%E2%80%93s_Medizinal-Pflanzen-112.jpg"},

  {"name":"Confrei","sci":"Symphytum officinale","emoji":"🌿","temp":"fria","elem":"terra","cat":"raiz",
   "desc":"Raiz de cura de Omolu para regeneração espiritual e cura de feridas sutis.",
   "spiritual":"Regeneração espiritual, cura de feridas e solidificação de proteções.",
   "bath_uses":["Regeneração","Cura de feridas","Solidificação"],"tea_uses":[],
   "can_fumigate":False,"fumig":"","orixas":["Omolu"],
   "compat":["Arnica","Espinheira-Santa","Copaíba"],"incompat":[],
   "preparo":"Apenas uso externo em banhos. Tóxica para uso interno.",
   "recommended":["banho"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/3/33/Symphytum_officinale_-_K%C3%B6hler%E2%80%93s_Medizinal-Pflanzen-137.jpg/640px-Symphytum_officinale_-_K%C3%B6hler%E2%80%93s_Medizinal-Pflanzen-137.jpg"},

  {"name":"Saião","sci":"Kalanchoe brasiliensis","emoji":"🌿","temp":"fria","elem":"água","cat":"folha",
   "desc":"Folha suculenta de Nanã e Iemanjá para cura, proteção e equilíbrio hídrico.",
   "spiritual":"Cura, proteção e equilíbrio das águas espirituais.",
   "bath_uses":["Cura","Proteção","Equilíbrio hídrico"],"tea_uses":["Gripe","Tosse","Cura"],
   "can_fumigate":False,"fumig":"","orixas":["Nanã","Iemanjá"],
   "compat":["Folha-da-Costa","Alfazema","Camomila"],"incompat":[],
   "preparo":"Folhas suculentas em banho ou chá de cura. Muito comum e segura.",
   "recommended":["banho","cha"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/b/b5/Kalanchoe_pinnata_ies.jpg/640px-Kalanchoe_pinnata_ies.jpg"},

  {"name":"Sucupira","sci":"Bowdichia virgilioides","emoji":"🌳","temp":"quente","elem":"terra","cat":"semente",
   "desc":"Semente e árvore sagrada de Oxóssi para força, saúde e proteção da mata.",
   "spiritual":"Força da mata, saúde espiritual e proteção de Oxóssi.",
   "bath_uses":["Força","Saúde","Proteção da mata"],"tea_uses":["Articulações","Saúde","Força"],
   "can_fumigate":True,"fumig":"Defumação de força e proteção da mata.",
   "orixas":["Oxóssi"],"compat":["Jatobá","Cipó-Caboclo","Cedro"],
   "incompat":[],"preparo":"Sementes em chá para articulações ou banho de força.",
   "recommended":["banho","cha"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/2/29/Bowdichia_virgilioides.jpg/640px-Bowdichia_virgilioides.jpg"},

  {"name":"Laranjeira","sci":"Citrus sinensis","emoji":"🍊","temp":"quente","elem":"fogo","cat":"flor",
   "desc":"Flor e folha da laranjeira de Oxum e Xangô para alegria, amor e prosperidade.",
   "spiritual":"Alegria, amor puro, prosperidade e força solar.",
   "bath_uses":["Alegria","Amor","Prosperidade"],"tea_uses":["Calma","Sono","Digestão"],
   "can_fumigate":True,"fumig":"Defumação de alegria e prosperidade com aroma cítrico.",
   "orixas":["Oxum","Xangô"],"compat":["Manjericão","Canela","Rosa Vermelha"],
   "incompat":[],"preparo":"Flores e folhas em banho ou chá. Aroma delicioso e elevante.",
   "recommended":["banho","cha","defumacao"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/4/43/Citrus_sinensis_flowers.jpg/640px-Citrus_sinensis_flowers.jpg"},

  {"name":"Limoeiro","sci":"Citrus limon","emoji":"🍋","temp":"quente","elem":"fogo","cat":"folha",
   "desc":"Folha e casca do limão de Ogum e Oxalá para limpeza, purificação e proteção.",
   "spiritual":"Limpeza ácida, purificação e corte de energias estagnadas.",
   "bath_uses":["Limpeza","Purificação","Corte de energias"],"tea_uses":["Imunidade","Vitamina C","Cura"],
   "can_fumigate":True,"fumig":"Defumação de limpeza com aroma cítrico refrescante.",
   "orixas":["Ogum","Oxalá"],"compat":["Alecrim","Hortelã","Capim-Limão"],
   "incompat":[],"preparo":"Folhas e cascas em banho de limpeza. Chá de limão clássico.",
   "recommended":["banho","cha","defumacao"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/b/b2/Lemon_flower.jpg/640px-Lemon_flower.jpg"},

  # ════════════════════════════════════════════════════════════
  # GRUPO 18 – Ervas e madeiras sagradas finais
  # ════════════════════════════════════════════════════════════
  {"name":"Cânfora-de-Bugre","sci":"Cryptocarya aschersoniana","emoji":"🌳","temp":"quente","elem":"fogo","cat":"casca",
   "desc":"Madeira nativa da mata atlântica de Oxóssi para proteção e força da floresta.",
   "spiritual":"Força e proteção da mata atlântica. Ligada aos caboclos e Oxóssi.",
   "bath_uses":["Proteção da mata","Força","Caboclos"],"tea_uses":[],
   "can_fumigate":True,"fumig":"Defumação de proteção da mata atlântica.",
   "orixas":["Oxóssi"],"compat":["Cedro","Jatobá","Cipó-Caboclo"],
   "incompat":[],"preparo":"Cascas em defumação ou banho de proteção da mata.",
   "recommended":["banho","defumacao"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/a/a0/Cryptocarya_aschersoniana_1.jpg/640px-Cryptocarya_aschersoniana_1.jpg"},

  {"name":"Gameleira","sci":"Ficus gomelleira","emoji":"🌳","temp":"neutra","elem":"terra","cat":"folha",
   "desc":"Árvore sagrada de Iroko (Tempo) e Oxalá, venerada como morada de orixás nos terreiros.",
   "spiritual":"Conexão com Iroko, ancestrais e orixás que habitam a gameleira sagrada.",
   "bath_uses":["Conexão ancestral","Força espiritual"],"tea_uses":[],
   "can_fumigate":False,"fumig":"","orixas":["Oxalá"],
   "compat":["Incenso (Olíbano)","Mirra","Cedro"],"incompat":[],
   "preparo":"Folhas colhidas com permissão ritual. Uso exclusivamente em banhos sagrados.",
   "recommended":["banho"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/9/91/Ficus_gomelleira.jpg/640px-Ficus_gomelleira.jpg"},

  {"name":"Dendezeiro","sci":"Elaeis guineensis","emoji":"🌴","temp":"quente","elem":"fogo","cat":"fruto",
   "desc":"Palmeira sagrada do azeite-de-dendê, elemento fundamental dos rituais de candomblé e umbanda.",
   "spiritual":"Força, axé e proteção de todos os orixás. O dendê é sagrado na tradição.",
   "bath_uses":["Força","Axé","Proteção de orixás"],"tea_uses":[],
   "can_fumigate":False,"fumig":"","orixas":["Exu","Ogum","Xangô","Oxum"],
   "compat":["Incenso (Olíbano)","Mirra"],"incompat":[],
   "preparo":"Folhas e frutos em oferendas e rituais. Óleo usado em axés e ebós.",
   "recommended":["banho"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/d/d1/Elaeis_guineensis_plantation.jpg/640px-Elaeis_guineensis_plantation.jpg"},

  {"name":"Coqueiro","sci":"Cocos nucifera","emoji":"🥥","temp":"fria","elem":"água","cat":"folha",
   "desc":"Palmeira de Iemanjá e Oxalá, símbolo de pureza, paz e conexão com as águas.",
   "spiritual":"Pureza, paz e axé das águas. O coco é usado em rituais de Iemanjá.",
   "bath_uses":["Pureza","Paz","Conexão com Iemanjá"],"tea_uses":["Hidratação","Saúde"],
   "can_fumigate":False,"fumig":"","orixas":["Iemanjá","Oxalá"],
   "compat":["Algas Marinhas","Rosa Branca","Alfazema"],"incompat":[],
   "preparo":"Água de coco em banhos sagrados. Folhas em rituais de Iemanjá.",
   "recommended":["banho","cha"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/f/f2/Coconut_on_tree_02.jpg/640px-Coconut_on_tree_02.jpg"},

  {"name":"Bananeira","sci":"Musa paradisiaca","emoji":"🍌","temp":"fria","elem":"água","cat":"folha",
   "desc":"Planta sagrada de Oxalá e Omolu, usada em banhos de saúde e proteção.",
   "spiritual":"Saúde, proteção e generosidade espiritual. Ligada a Oxalá e Omolu.",
   "bath_uses":["Saúde","Proteção","Generosidade"],"tea_uses":[],
   "can_fumigate":False,"fumig":"","orixas":["Oxalá","Omolu"],
   "compat":["Alfazema","Rosa Branca","Camomila"],"incompat":[],
   "preparo":"Folhas em banhos de saúde. Flor da bananeira em rituais especiais.",
   "recommended":["banho"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/8/8a/Banana-Platano.jpg/640px-Banana-Platano.jpg"},

  {"name":"Mandioquinha","sci":"Arracacia xanthorrhiza","emoji":"🌿","temp":"neutra","elem":"terra","cat":"raiz",
   "desc":"Raiz de Omolu e Oxalá usada em rituais de cura, saúde e oferendas.",
   "spiritual":"Saúde, cura e conexão com as raízes espirituais ancestrais.",
   "bath_uses":["Cura","Saúde","Enraizamento"],"tea_uses":["Saúde","Nutrição"],
   "can_fumigate":False,"fumig":"","orixas":["Omolu","Oxalá"],
   "compat":["Espinheira-Santa","Boldo","Transagem"],"incompat":[],
   "preparo":"Raiz em banho de cura. Alimento sagrado oferecido a Omolu.",
   "recommended":["banho"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/3/3c/Arracacia_xanthorrhiza.jpg/640px-Arracacia_xanthorrhiza.jpg"},

  {"name":"Pitanga","sci":"Eugenia uniflora","emoji":"🍒","temp":"quente","elem":"fogo","cat":"folha",
   "desc":"Árvore frutífera nativa do Brasil de Oxum e Xangô para alegria, saúde e prosperidade.",
   "spiritual":"Alegria, saúde, prosperidade e proteção. Fruto e folha usados em rituais.",
   "bath_uses":["Alegria","Saúde","Prosperidade"],"tea_uses":["Pressão arterial","Antioxidante","Saúde"],
   "can_fumigate":False,"fumig":"","orixas":["Oxum","Xangô"],
   "compat":["Laranjeira","Manjericão","Rosa Amarela"],"incompat":[],
   "preparo":"Folhas em chá medicinal ou banho de alegria e saúde.",
   "recommended":["banho","cha"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/d/d5/Surinam-Cherry.jpg/640px-Surinam-Cherry.jpg"},

  {"name":"Goiabeira","sci":"Psidium guajava","emoji":"🌿","temp":"quente","elem":"terra","cat":"folha",
   "desc":"Árvore de Omolu e Oxóssi muito usada para cura, proteção e saúde na medicina popular.",
   "spiritual":"Cura de doenças, proteção e saúde espiritual.",
   "bath_uses":["Cura","Proteção","Saúde"],"tea_uses":["Diarreia","Imunidade","Anti-inflamatório"],
   "can_fumigate":False,"fumig":"","orixas":["Omolu","Oxóssi"],
   "compat":["Assa-Peixe","Espinheira-Santa","Boldo"],"incompat":[],
   "preparo":"Folhas em chá para diarreia ou banho de cura e proteção.",
   "recommended":["banho","cha"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/6/6a/Psidium_guajava.jpg/640px-Psidium_guajava.jpg"},

  {"name":"Mangueira","sci":"Mangifera indica","emoji":"🥭","temp":"quente","elem":"fogo","cat":"folha",
   "desc":"Árvore majestosa de Xangô e Ogum para força, vitória e fartura espiritual.",
   "spiritual":"Força, vitória e fartura. Árvore de Xangô e Ogum.",
   "bath_uses":["Força","Vitória","Fartura"],"tea_uses":["Imunidade","Saúde"],
   "can_fumigate":False,"fumig":"","orixas":["Xangô","Ogum"],
   "compat":["Louro","Alecrim","Pitanga"],"incompat":[],
   "preparo":"Folhas jovens em chá ou banho de força e vitória.",
   "recommended":["banho","cha"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/4/47/Mango_flowers_at_Saligao%2C_Goa.jpg/640px-Mango_flowers_at_Saligao%2C_Goa.jpg"},

  {"name":"Melão-de-São-Caetano","sci":"Momordica charantia","emoji":"🌿","temp":"quente","elem":"fogo","cat":"erva",
   "desc":"Trepadeira de Ogum e Xangô para proteção, purificação e corte de energias negativas.",
   "spiritual":"Proteção, purificação e corte de energias negativas muito intensa.",
   "bath_uses":["Proteção","Purificação","Corte de energias"],"tea_uses":["Diabetes","Imunidade"],
   "can_fumigate":True,"fumig":"Defumação de corte e purificação intensa.",
   "orixas":["Ogum","Xangô"],"compat":["Arruda","Guiné","Losna"],
   "incompat":[],"preparo":"Frutos e folhas em banho. Contraindicado em gestantes.",
   "recommended":["banho","defumacao"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/3/3a/Momordica_charantia.jpg/640px-Momordica_charantia.jpg"},

  {"name":"Quioiô","sci":"Ocimum gratissimum","emoji":"🌿","temp":"quente","elem":"fogo","cat":"erva",
   "desc":"Alfavacão africano de Xangô e Ogum para proteção, força e descarrego espiritual.",
   "spiritual":"Proteção, força e descarrego. Muito usado no candomblé como erva de Xangô.",
   "bath_uses":["Proteção","Força","Descarrego"],"tea_uses":["Gripe","Imunidade","Febre"],
   "can_fumigate":True,"fumig":"Defumação de proteção e força espiritual.",
   "orixas":["Xangô","Ogum"],"compat":["Alecrim","Arruda","Guiné"],
   "incompat":[],"preparo":"Fresco ou seco em banho ou defumação de proteção.",
   "recommended":["banho","cha","defumacao"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/e/e3/Ocimum_gratissimum.jpg/640px-Ocimum_gratissimum.jpg"},

  {"name":"Erva-Baleeira","sci":"Varronia curassavica","emoji":"🌿","temp":"quente","elem":"fogo","cat":"erva",
   "desc":"Erva de Ogum usada para cura de dores e proteção espiritual do corpo físico.",
   "spiritual":"Cura do corpo físico-espiritual e proteção de Ogum.",
   "bath_uses":["Cura corporal","Proteção","Força"],"tea_uses":["Dor","Anti-inflamatório","Cura"],
   "can_fumigate":True,"fumig":"Defumação de cura e proteção corporal.",
   "orixas":["Ogum"],"compat":["Arnica","Confrei","Espinheira-Santa"],
   "incompat":[],"preparo":"Folhas em banho de cura ou chá anti-inflamatório.",
   "recommended":["banho","cha"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/e/e7/Varronia_curassavica.jpg/640px-Varronia_curassavica.jpg"},

  {"name":"Cipó-Cabeludo","sci":"Mikania hirsutissima","emoji":"🌿","temp":"fria","elem":"água","cat":"erva",
   "desc":"Trepadeira da mata de Oxóssi para equilíbrio, cura e conexão com a floresta.",
   "spiritual":"Equilíbrio, cura e conexão com os espíritos da floresta.",
   "bath_uses":["Equilíbrio","Cura","Conexão com a floresta"],"tea_uses":["Reumatismo","Dor"],
   "can_fumigate":False,"fumig":"","orixas":["Oxóssi"],
   "compat":["Samambaia","Cipó-Caboclo","Guaco"],"incompat":[],
   "preparo":"Folhas em banho de equilíbrio ou chá para reumatismo.",
   "recommended":["banho","cha"],"img_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/6/65/Mikania_glomerata.jpg/640px-Mikania_glomerata.jpg"},

    ]
# ── Inicialização e execução ──────────────────────────────────────────────────

# Também executado quando o módulo é carregado pelo Gunicorn.
init_db()

if __name__ == "__main__":
    run_port = int(os.environ.get("PORT", "5000"))
    print("=" * 55)
    print("  Enciclopedia das Ervas Sagradas")
    print(f"  http://localhost:{run_port}")
    print("=" * 55)
    app.run(debug=APP_ENV == "development", host=os.environ.get("HOST", "127.0.0.1"), port=run_port)
