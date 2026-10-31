
import os
import sqlite3
import uuid
from pathlib import Path
from functools import wraps

from flask import (
    Flask, request, redirect, url_for,
    session, flash, render_template_string
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "troque-esta-chave-secreta")

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "static" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

DB = BASE_DIR / "loja.db"
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@jottastore.com").lower()
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "troque-esta-senha")

def conectar():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con

def iniciar_banco():
    with conectar() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                senha TEXT NOT NULL
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS produtos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                descricao TEXT,
                preco REAL NOT NULL,
                estoque INTEGER NOT NULL DEFAULT 0,
                foto TEXT
            )
        """)

iniciar_banco()

def login_obrigatorio(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not session.get("email"):
            return redirect(url_for("login"))
        return func(*args, **kwargs)
    return wrapper

def admin_obrigatorio(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not session.get("admin"):
            return redirect(url_for("admin_login"))
        return func(*args, **kwargs)
    return wrapper

MODELO = """
<!DOCTYPE html>
<html lang="pt-br">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>JOTTA STORE</title>
<style>
*{box-sizing:border-box}
body{margin:0;background:#f5f5f5;color:#222;font-family:Arial}
header{background:#111;color:white;padding:20px;text-align:center}
header h1{margin:0;color:#d6ad60}
nav{background:#222;padding:13px;text-align:center}
nav a{color:white;text-decoration:none;margin:8px;font-size:14px}
main{max-width:1050px;margin:25px auto;padding:15px}
.card{background:white;padding:20px;border-radius:12px;margin-bottom:18px}
input,textarea,button{width:100%;padding:12px;margin:7px 0;border:1px solid #ddd;border-radius:7px}
button{background:#111;color:white;border:0;cursor:pointer}
button:hover{background:#444}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:18px}
.produto{background:white;border-radius:12px;padding:12px}
.produto img{width:100%;height:220px;object-fit:cover;border-radius:8px}
.preco{font-size:20px;font-weight:bold;color:#9b742e}
a{color:#9b742e}
.mensagem{padding:10px;background:#eee;margin:10px 0;border-radius:7px}
</style>
</head>
<body>
<header><h1>JOTTA STORE</h1><p>Estilo que combina com você</p></header>
<nav>
<a href="/">Início</a>
<a href="/carrinho">Carrinho</a>
{% if session.get('email') %}<a href="/sair">Sair</a>{% else %}
<a href="/login">Entrar</a><a href="/cadastro">Criar conta</a>{% endif %}
<a href="/admin/login">Administrador</a>
</nav>
<main>
{% with mensagens = get_flashed_messages() %}
{% for m in mensagens %}<div class="mensagem">{{m}}</div>{% endfor %}
{% endwith %}
{{conteudo|safe}}
</main>
</body>
</html>
"""

def pagina(conteudo):
    return render_template_string(MODELO, conteudo=conteudo)

@app.route("/")
def inicio():
    with conectar() as con:
        produtos = con.execute("SELECT * FROM produtos ORDER BY id DESC").fetchall()

    html = "<h2>Nossa coleção</h2><div class='grid'>"
    for p in produtos:
        foto = f"/static/uploads/{p['foto']}" if p["foto"] else ""
        html += f"""
        <div class='produto'>
        <img src='{foto}' alt='Produto'>
        <h3>{p['nome']}</h3>
        <p>{p['descricao'] or ''}</p>
        <p class='preco'>R$ {p['preco']:.2f}</p>
        <p>Estoque: {p['estoque']}</p>
        <form method='post' action='/adicionar/{p['id']}'>
        <button>Adicionar ao carrinho</button>
        </form></div>
        """
    html += "</div>"
    if not produtos:
        html = "<h2>Nossa coleção</h2><p>Nenhum produto cadastrado ainda.</p>"
    return pagina(html)

@app.route("/cadastro", methods=["GET", "POST"])
def cadastro():
    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        email = request.form.get("email", "").strip().lower()
        senha = request.form.get("senha", "")

        if not nome or not email or len(senha) < 6:
            flash("Preencha os dados. A senha precisa ter pelo menos 6 caracteres.")
            return redirect(url_for("cadastro"))

        try:
            with conectar() as con:
                con.execute(
                    "INSERT INTO usuarios (nome,email,senha) VALUES (?,?,?)",
                    (nome, email, generate_password_hash(senha))
                )
            session["email"] = email
            session["nome"] = nome
            flash("Conta criada com sucesso!")
            return redirect(url_for("inicio"))
        except sqlite3.IntegrityError:
            flash("Este Gmail já está cadastrado.")

    return pagina("""
    <div class='card'><h2>Criar conta</h2>
    <form method='post'>
    <input name='nome' placeholder='Seu nome' required>
    <input name='email' type='email' placeholder='Seu Gmail' required>
    <input name='senha' type='password' placeholder='Crie uma senha (mínimo 6 caracteres)' required>
    <button>Criar minha conta</button>
    </form><p>Já tem conta? <a href='/login'>Entrar</a></p></div>
    """)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        senha = request.form.get("senha", "")

        with conectar() as con:
            usuario = con.execute(
                "SELECT * FROM usuarios WHERE email=?", (email,)
            ).fetchone()

        if usuario and check_password_hash(usuario["senha"], senha):
            session.clear()
            session["email"] = usuario["email"]
            session["nome"] = usuario["nome"]
            return redirect(url_for("inicio"))

        flash("Gmail ou senha incorretos.")

    return pagina("""
    <div class='card'><h2>Entrar na JOTTA STORE</h2>
    <form method='post'>
    <input name='email' type='email' placeholder='Seu Gmail' required>
    <input name='senha' type='password' placeholder='Sua senha' required>
    <button>Entrar</button>
    </form><p>Não tem conta? <a href='/cadastro'>Cadastre-se</a></p></div>
    """)

@app.route("/sair")
def sair():
    session.clear()
    return redirect(url_for("inicio"))

@app.route("/adicionar/<int:produto_id>", methods=["POST"])
@login_obrigatorio
def adicionar(produto_id):
    with conectar() as con:
        produto = con.execute(
            "SELECT * FROM produtos WHERE id=?", (produto_id,)
        ).fetchone()

    if not produto or produto["estoque"] <= 0:
        flash("Produto indisponível.")
    else:
        carrinho = session.get("carrinho", {})
        chave = str(produto_id)
        carrinho[chave] = carrinho.get(chave, 0) + 1
        session["carrinho"] = carrinho
        flash("Produto adicionado ao carrinho!")

    return redirect(url_for("inicio"))

@app.route("/carrinho")
@login_obrigatorio
def carrinho():
    carrinho = session.get("carrinho", {})
    html = "<div class='card'><h2>Meu carrinho</h2>"
    total = 0

    with conectar() as con:
        for pid, quantidade in carrinho.items():
            produto = con.execute(
                "SELECT * FROM produtos WHERE id=?", (int(pid),)
            ).fetchone()
            if produto:
                subtotal = produto["preco"] * quantidade
                total += subtotal
                html += f"<p>{produto['nome']} — {quantidade} unidade(s) — R$ {subtotal:.2f}</p>"

    html += f"<h3>Total: R$ {total:.2f}</h3>"
    html += "<p>Entre em contato com a loja para finalizar seu pedido.</p>"
    html += "<a href='/'>Continuar comprando</a></div>"
    return pagina(html)

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        senha = request.form.get("senha", "")

        if email == ADMIN_EMAIL and senha == ADMIN_PASSWORD:
            session.clear()
            session["admin"] = True
            return redirect(url_for("admin"))

        flash("Dados de administrador incorretos.")

    return pagina("""
    <div class='card'><h2>Área administrativa</h2>
    <form method='post'>
    <input name='email' type='email' placeholder='E-mail do administrador' required>
    <input name='senha' type='password' placeholder='Senha do administrador' required>
    <button>Entrar no painel</button>
    </form></div>
    """)

@app.route("/admin")
@admin_obrigatorio
def admin():
    with conectar() as con:
        produtos = con.execute("SELECT * FROM produtos ORDER BY id DESC").fetchall()

    html = """
    <div class='card'><h2>Painel da JOTTA STORE</h2>
    <h3>Cadastrar produto</h3>
    <form method='post' action='/admin/adicionar' enctype='multipart/form-data'>
    <input name='nome' placeholder='Nome da roupa' required>
    <textarea name='descricao' placeholder='Descrição'></textarea>
    <input name='preco' type='number' step='0.01' min='0' placeholder='Preço' required>
    <input name='estoque' type='number' min='0' placeholder='Quantidade em estoque' required>
    <input name='foto' type='file' accept='image/*'>
    <button>Cadastrar produto</button></form>
    <a href='/admin/sair'>Sair do administrador</a></div>
    <h2>Produtos cadastrados</h2>
    """

    for p in produtos:
        html += f"""
        <div class='card'><h3>{p['nome']}</h3>
        <p>Preço: R$ {p['preco']:.2f} | Estoque: {p['estoque']}</p>
        <form method='post' action='/admin/editar/{p['id']}'>
        <input name='nome' value='{p['nome']}' required>
        <textarea name='descricao'>{p['descricao'] or ''}</textarea>
        <input name='preco' type='number' step='0.01' min='0' value='{p['preco']}' required>
        <input name='estoque' type='number' min='0' value='{p['estoque']}' required>
        <button>Salvar alterações</button></form>
        <form method='post' action='/admin/excluir/{p['id']}'>
        <button>Excluir produto</button></form></div>
        """
    return pagina(html)

@app.route("/admin/adicionar", methods=["POST"])
@admin_obrigatorio
def admin_adicionar():
    nome = request.form.get("nome", "").strip()
    descricao = request.form.get("descricao", "").strip()

    try:
        preco = float(request.form.get("preco", "0"))
        estoque = int(request.form.get("estoque", "0"))
        if preco < 0 or estoque < 0:
            raise ValueError()
    except ValueError:
        flash("Preço ou estoque inválido.")
        return redirect(url_for("admin"))

    foto = request.files.get("foto")
    nome_foto = None

    if foto and foto.filename:
        extensao = Path(secure_filename(foto.filename)).suffix.lower()
        if extensao not in [".jpg", ".jpeg", ".png", ".webp"]:
            flash("Use uma imagem JPG, PNG ou WEBP.")
            return redirect(url_for("admin"))
        nome_foto = uuid.uuid4().hex + extensao
        foto.save(UPLOAD_DIR / nome_foto)

    with conectar() as con:
        con.execute(
            "INSERT INTO produtos (nome,descricao,preco,estoque,foto) VALUES (?,?,?,?,?)",
            (nome, descricao, preco, estoque, nome_foto)
        )

    flash("Produto cadastrado!")
    return redirect(url_for("admin"))

@app.route("/admin/editar/<int:produto_id>", methods=["POST"])
@admin_obrigatorio
def admin_editar(produto_id):
    try:
        nome = request.form.get("nome", "").strip()
        descricao = request.form.get("descricao", "").strip()
        preco = float(request.form.get("preco", "0"))
        estoque = int(request.form.get("estoque", "0"))
        if not nome or preco < 0 or estoque < 0:
            raise ValueError()
    except ValueError:
        flash("Confira os dados do produto.")
        return redirect(url_for("admin"))

    with conectar() as con:
        con.execute(
            "UPDATE produtos SET nome=?,descricao=?,preco=?,estoque=? WHERE id=?",
            (nome, descricao, preco, estoque, produto_id)
        )

    flash("Produto atualizado!")
    return redirect(url_for("admin"))

@app.route("/admin/excluir/<int:produto_id>", methods=["POST"])
@admin_obrigatorio
def admin_excluir(produto_id):
    with conectar() as con:
        con.execute("DELETE FROM produtos WHERE id=?", (produto_id,))
    flash("Produto excluído.")
    return redirect(url_for("admin"))

@app.route("/admin/sair")
def admin_sair():
    session.clear()
    return redirect(url_for("inicio"))

if __name__ == "__main__":
    app.run(debug=True)
