
import os
import sqlite3
import secrets
import uuid
import io
import base64
from functools import wraps
from pathlib import Path

import qrcode
from flask import Flask, request, redirect, url_for, session, flash, render_template_string, send_from_directory, abort
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "troque-esta-chave-secreta")

PIX_KEY = os.environ.get("PIX_KEY", "maiaj2733@gmail.com")
PIX_NAME = "JOTTA STORE"
PIX_CITY = "TEIXEIRA DE FREITAS"

ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "troque-esta-senha")

DB = "loja.db"
UPLOAD = Path("static/uploads")
UPLOAD.mkdir(parents=True, exist_ok=True)

def conectar():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con

def iniciar():
    with conectar() as con:
        con.execute("""
        CREATE TABLE IF NOT EXISTS produtos(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT,
            descricao TEXT,
            preco REAL,
            estoque INTEGER,
            imagem TEXT
        )""")
        con.execute("""
        CREATE TABLE IF NOT EXISTS pedidos(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente TEXT,
            telefone TEXT,
            produtos TEXT,
            total REAL,
            pix TEXT,
            status TEXT DEFAULT 'Aguardando pagamento'
        )""")

iniciar()

def dinheiro(valor):
    return f"R$ {valor:.2f}".replace(".", ",")

def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("admin"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper

def tlv(tag, value):
    value = str(value)
    return f"{tag}{len(value):02d}{value}"

def crc16(payload):
    crc = 0xFFFF
    for byte in payload.encode():
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return f"{crc:04X}"

def gerar_pix(valor, txid):
    gui = tlv("00", "br.gov.bcb.pix") + tlv("01", PIX_KEY)
    merchant = tlv("26", gui)

    payload = (
        tlv("00", "01") +
        tlv("01", "12") +
        merchant +
        tlv("52", "0000") +
        tlv("53", "986") +
        tlv("54", f"{valor:.2f}") +
        tlv("58", "BR") +
        tlv("59", PIX_NAME) +
        tlv("60", PIX_CITY) +
        tlv("62", tlv("05", txid[:25]))
    )

    parcial = payload + "6304"
    return parcial + crc16(parcial)

def gerar_qr(codigo):
    imagem = qrcode.make(codigo)
    buffer = io.BytesIO()
    imagem.save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()

CSS = """
<style>
*{box-sizing:border-box}
body{margin:0;background:#f5f5f5;color:#171717;font-family:Arial}
header{background:#111;color:white;padding:22px;text-align:center}
header h1{letter-spacing:3px;margin:0}
nav{background:white;padding:15px;text-align:center}
nav a{color:#111;margin:10px;text-decoration:none;font-weight:bold}
main{max-width:1100px;margin:30px auto;padding:15px}
.banner{background:#111;color:white;padding:45px 25px;border-radius:12px;margin-bottom:25px}
.banner h2{font-size:35px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:20px}
.card{background:white;border-radius:10px;overflow:hidden;padding-bottom:15px}
.card img{width:100%;height:240px;object-fit:cover}
.card h3,.card p{padding:0 15px}
.card button{margin-left:15px}
button,.btn{background:#111;color:white;border:0;padding:12px 18px;border-radius:6px;cursor:pointer;text-decoration:none;display:inline-block}
input,textarea,select{width:100%;padding:12px;margin:8px 0 15px;border:1px solid #ccc;border-radius:6px}
.box{background:white;padding:22px;border-radius:10px;margin-bottom:20px}
table{width:100%;background:white;border-collapse:collapse}
td,th{padding:12px;border-bottom:1px solid #ddd;text-align:left}
.qr{width:230px;max-width:100%}
footer{text-align:center;padding:30px;color:#777}
</style>
"""

def pagina(titulo, conteudo, **dados):
    return render_template_string("""
    <!DOCTYPE html><html lang="pt-br">
    <head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
    <title>{{titulo}} - JOTTA STORE</title>
    """ + CSS + """
    </head><body>
    <header><h1>JOTTA STORE</h1><p>Vista seu estilo.</p></header>
    <nav><a href="/">INÍCIO</a><a href="/carrinho">CARRINHO</a><a href="/admin">ADMIN</a></nav>
    <main><h2>{{titulo}}</h2>
    {% with msgs=get_flashed_messages() %}{% for m in msgs %}<p>{{m}}</p>{% endfor %}{% endwith %}
    """ + conteudo + """
    </main><footer>JOTTA STORE © 2026</footer></body></html>
    """, titulo=titulo, **dados)

@app.route("/")
def home():
    with conectar() as con:
        produtos = con.execute("SELECT * FROM produtos ORDER BY id DESC").fetchall()

    html = """
    <section class="banner">
    <h2>Nova coleção chegou!</h2>
    <p>Encontre seu estilo na JOTTA STORE.</p>
    </section>
    <div class="grid">
    {% for p in produtos %}
    <div class="card">
    {% if p['imagem'] %}
    <img src="{{url_for('imagem', nome=p['imagem'])}}">
    {% endif %}
    <h3>{{p['nome']}}</h3>
    <p>{{p['descricao']}}</p>
    <p><b>{{dinheiro(p['preco'])}}</b></p>
    <p>Estoque: {{p['estoque']}}</p>
    <form method="post" action="/adicionar/{{p['id']}}">
    <input type="number" name="quantidade" value="1" min="1" max="{{p['estoque']}}" required>
    <button {% if p['estoque'] < 1 %}disabled{% endif %}>Adicionar</button>
    </form></div>
    {% endfor %}
    </div>
    """
    return pagina("Nossa coleção", html, produtos=produtos, dinheiro=dinheiro)

@app.route("/imagem/<nome>")
def imagem(nome):
    return send_from_directory(UPLOAD, nome)

@app.post("/adicionar/<int:id>")
def adicionar(id):
    quantidade = max(1, request.form.get("quantidade", 1, type=int))
    with conectar() as con:
        p = con.execute("SELECT * FROM produtos WHERE id=?", (id,)).fetchone()

    if not p or p["estoque"] < quantidade:
        flash("Estoque insuficiente.")
        return redirect("/")

    carrinho = session.get("carrinho", {})
    carrinho[str(id)] = carrinho.get(str(id), 0) + quantidade
    session["carrinho"] = carrinho
    flash("Produto adicionado!")
    return redirect("/")

@app.route("/carrinho")
def carrinho():
    itens = []
    total = 0
    with conectar() as con:
        for pid, quantidade in session.get("carrinho", {}).items():
            p = con.execute("SELECT * FROM produtos WHERE id=?", (pid,)).fetchone()
            if p:
                subtotal = p["preco"] * quantidade
                total += subtotal
                itens.append((p, quantidade, subtotal))

    html = """
    {% for p,q,s in itens %}
    <div class="box">
    <h3>{{p['nome']}}</h3>
    <p>Quantidade: {{q}}</p>
    <p>Subtotal: {{dinheiro(s)}}</p>
    <a href="/remover/{{p['id']}}">Remover</a>
    </div>
    {% endfor %}
    <div class="box"><h2>Total: {{dinheiro(total)}}</h2>
    {% if itens %}<a class="btn" href="/checkout">FINALIZAR COMPRA</a>{% else %}Carrinho vazio{% endif %}
    </div>
    """
    return pagina("Meu carrinho", html, itens=itens, total=total, dinheiro=dinheiro)

@app.route("/remover/<int:id>")
def remover(id):
    carrinho = session.get("carrinho", {})
    carrinho.pop(str(id), None)
    session["carrinho"] = carrinho
    return redirect("/carrinho")

@app.route("/checkout", methods=["GET", "POST"])
def checkout():
    carrinho = session.get("carrinho", {})
    if not carrinho:
        return redirect("/")

    itens = []
    total = 0

    with conectar() as con:
        for pid, quantidade in carrinho.items():
            p = con.execute("SELECT * FROM produtos WHERE id=?", (pid,)).fetchone()
            if not p or quantidade > p["estoque"]:
                flash("Estoque insuficiente. Revise seu carrinho.")
                return redirect("/carrinho")
            itens.append((p, quantidade))
            total += p["preco"] * quantidade

    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        telefone = request.form.get("telefone", "").strip()

        if not nome or not telefone:
            flash("Preencha seus dados.")
            return redirect("/checkout")

        txid = uuid.uuid4().hex[:20].upper()
        pix = gerar_pix(total, txid)
        resumo = ", ".join(f"{p['nome']} x{q}" for p,q in itens)

        with conectar() as con:
            cur = con.execute("""
            INSERT INTO pedidos(cliente,telefone,produtos,total,pix)
            VALUES(?,?,?,?,?)
            """, (nome, telefone, resumo, total, pix))
            pedido_id = cur.lastrowid

        session["carrinho"] = {}
        return redirect(f"/pedido/{pedido_id}")

    html = """
    <div class="box">
    <h3>Total: {{dinheiro(total)}}</h3>
    <form method="post">
    <label>Nome completo</label><input name="nome" required>
    <label>WhatsApp</label><input name="telefone" required>
    <button>GERAR PIX</button>
    </form></div>
    """
    return pagina("Finalizar compra", html, total=total, dinheiro=dinheiro)

@app.route("/pedido/<int:id>")
def pedido(id):
    with conectar() as con:
        p = con.execute("SELECT * FROM pedidos WHERE id=?", (id,)).fetchone()
    if not p:
        abort(404)

    qr = gerar_qr(p["pix"])
    html = """
    <div class="box" style="text-align:center">
    <h2>Pedido #{{p['id']}} criado!</h2>
    <p>Total: <b>{{dinheiro(p['total'])}}</b></p>
    <p>Escaneie o QR Code:</p>
    <img class="qr" src="{{qr}}">
    <p>Código Pix copia e cola:</p>
    <textarea id="pix" rows="5" readonly>{{p['pix']}}</textarea>
    <button onclick="navigator.clipboard.writeText(document.getElementById('pix').value).then(()=>alert('Pix copiado!'))">COPIAR PIX</button>
    <p>Após pagar, envie o comprovante para a loja.</p>
    <p><b>O sistema não confirma pagamentos automaticamente.</b></p>
    </div>
    """
    return pagina("Pagamento Pix", html, p=p, qr=qr, dinheiro=dinheiro)

@app.route("/admin", methods=["GET", "POST"])
def login():
    if session.get("admin"):
        return redirect("/painel")
    if request.method == "POST":
        if request.form.get("usuario") == ADMIN_USER and request.form.get("senha") == ADMIN_PASSWORD:
            session["admin"] = True
            return redirect("/painel")
        flash("Login incorreto.")
    html = """
    <div class="box"><form method="post">
    <label>Usuário</label><input name="usuario" required>
    <label>Senha</label><input name="senha" type="password" required>
    <button>ENTRAR</button></form></div>
    """
    return pagina("Área administrativa", html)

@app.route("/painel")
@admin_required
def painel():
    with conectar() as con:
        produtos = con.execute("SELECT * FROM produtos ORDER BY id DESC").fetchall()
        pedidos = con.execute("SELECT * FROM pedidos ORDER BY id DESC").fetchall()

    html = """
    <div class="box"><a class="btn" href="/novo-produto">CADASTRAR PRODUTO</a>
    <a class="btn" href="/sair">SAIR</a></div>
    <h3>Produtos</h3><table><tr><th>Nome</th><th>Preço</th><th>Estoque</th><th></th></tr>
    {% for p in produtos %}
    <tr><td>{{p['nome']}}</td><td>{{dinheiro(p['preco'])}}</td>
    <td>{{p['estoque']}}</td><td><a href="/editar/{{p['id']}}">Editar</a></td></tr>
    {% endfor %}</table>
    <h3>Pedidos</h3><table><tr><th>Número</th><th>Cliente</th><th>Total</th><th>Status</th></tr>
    {% for p in pedidos %}
    <tr><td>#{{p['id']}}</td><td>{{p['cliente']}}</td><td>{{dinheiro(p['total'])}}</td><td>{{p['status']}}</td></tr>
    {% endfor %}</table>
    """
    return pagina("Painel da loja", html, produtos=produtos, pedidos=pedidos, dinheiro=dinheiro)

def formulario_produto(p=None):
    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        descricao = request.form.get("descricao", "").strip()
        try:
            preco = float(request.form.get("preco", "0").replace(",", "."))
            estoque = int(request.form.get("estoque", "0"))
            if not nome or preco < 0 or estoque < 0:
                raise ValueError()
        except ValueError:
            flash("Confira preço, nome e estoque.")
            return None

        foto = p["imagem"] if p else ""
        arquivo = request.files.get("imagem")
        if arquivo and arquivo.filename:
            ext = arquivo.filename.rsplit(".", 1)[-1].lower()
            if ext not in ("png", "jpg", "jpeg", "webp"):
                flash("Envie uma imagem PNG, JPG ou WEBP.")
                return None
            foto = secrets.token_hex(12) + "." + ext
            arquivo.save(UPLOAD / foto)

        with conectar() as con:
            if p:
                con.execute("UPDATE produtos SET nome=?,descricao=?,preco=?,estoque=?,imagem=? WHERE id=?",
                            (nome, descricao, preco, estoque, foto, p["id"]))
            else:
                con.execute("INSERT INTO produtos(nome,descricao,preco,estoque,imagem) VALUES(?,?,?,?,?)",
                            (nome, descricao, preco, estoque, foto))
        return True
    return False

FORM = """
<div class="box"><form method="post" enctype="multipart/form-data">
<label>Nome</label><input name="nome" value="{{p['nome'] if p else ''}}" required>
<label>Descrição</label><textarea name="descricao">{{p['descricao'] if p else ''}}</textarea>
<label>Preço</label><input name="preco" value="{{p['preco'] if p else ''}}" required>
<label>Estoque</label><input name="estoque" type="number" min="0" value="{{p['estoque'] if p else 0}}" required>
<label>Foto</label><input name="imagem" type="file" accept="image/*">
<button>SALVAR</button></form></div>
"""

@app.route("/novo-produto", methods=["GET", "POST"])
@admin_required
def novo_produto():
    resultado = formulario_produto()
    if resultado:
        flash("Produto cadastrado!")
        return redirect("/painel")
    return pagina("Novo produto", FORM, p=None)

@app.route("/editar/<int:id>", methods=["GET", "POST"])
@admin_required
def editar(id):
    with conectar() as con:
        p = con.execute("SELECT * FROM produtos WHERE id=?", (id,)).fetchone()
    if not p:
        abort(404)
    resultado = formulario_produto(p)
    if resultado:
        flash("Produto atualizado!")
        return redirect("/painel")
    return pagina("Editar produto", FORM, p=p)

@app.route("/sair")
def sair():
    session.clear()
    return redirect("/")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
