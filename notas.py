
import os
import sqlite3
from functools import wraps
from flask import (
    Flask, request, redirect, session,
    flash, render_template_string, url_for
)
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "devconnect-secret-change-me")

DB = "devconnect.db"


def db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = db()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL,
        bio TEXT DEFAULT '',
        skills TEXT DEFAULT ''
    );

    CREATE TABLE IF NOT EXISTS projects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        description TEXT NOT NULL,
        budget TEXT DEFAULT '',
        status TEXT DEFAULT 'Aberto'
    );

    CREATE TABLE IF NOT EXISTS proposals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id INTEGER NOT NULL,
        developer_id INTEGER NOT NULL,
        message TEXT NOT NULL,
        price TEXT DEFAULT '',
        UNIQUE(project_id, developer_id)
    );

    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sender_id INTEGER NOT NULL,
        receiver_id INTEGER NOT NULL,
        message TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS reviews (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        reviewer_id INTEGER NOT NULL,
        developer_id INTEGER NOT NULL,
        rating INTEGER NOT NULL,
        comment TEXT DEFAULT ''
    );
    """)
    conn.commit()
    conn.close()


init_db()


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            flash("Faça login para continuar.")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper


def current_user():
    if not session.get("user_id"):
        return None
    conn = db()
    user = conn.execute(
        "SELECT * FROM users WHERE id=?",
        (session["user_id"],)
    ).fetchone()
    conn.close()
    return user


BASE = """
<!DOCTYPE html>
<html lang="pt-br">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ title }} | DevConnect</title>
<style>
*{box-sizing:border-box}
body{margin:0;background:#0b1020;color:#f5f6fa;font-family:Arial,sans-serif}
nav{background:#111a30;padding:18px 6%;display:flex;justify-content:space-between;align-items:center;gap:15px;flex-wrap:wrap}
.logo{font-size:24px;font-weight:bold;color:#a78bfa;text-decoration:none}
nav a{color:#ddd;text-decoration:none;margin-left:15px}
.container{max-width:1050px;margin:35px auto;padding:0 18px}
h1,h2{color:#fff}
p{color:#b9c1d3;line-height:1.6}
.card{background:#151e34;border:1px solid #293653;padding:22px;border-radius:14px;margin:15px 0}
input,textarea,select{width:100%;padding:13px;margin:9px 0 15px;background:#0d1528;color:white;border:1px solid #394765;border-radius:8px}
textarea{min-height:110px}
button,.btn{background:#7c3aed;color:white;border:0;padding:12px 18px;border-radius:8px;cursor:pointer;text-decoration:none;display:inline-block;font-weight:bold}
button:hover,.btn:hover{background:#6d28d9}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:15px}
.tag{background:#292044;color:#c4b5fd;padding:6px 10px;border-radius:20px;font-size:12px}
.flash{background:#35274c;padding:12px;border-radius:8px;margin:12px 0}
small{color:#9ca3af}
a{color:#c4b5fd}
footer{text-align:center;color:#77839d;padding:35px}
</style>
</head>
<body>
<nav>
<a class="logo" href="{{ url_for('home') }}">DevConnect.</a>
<div>
{% if user %}
<a href="{{ url_for('home') }}">Início</a>
<a href="{{ url_for('projects') }}">Projetos</a>
<a href="{{ url_for('developers') }}">Desenvolvedores</a>
<a href="{{ url_for('inbox') }}">Mensagens</a>
<a href="{{ url_for('logout') }}">Sair</a>
{% else %}
<a href="{{ url_for('login') }}">Entrar</a>
<a href="{{ url_for('register') }}">Cadastrar</a>
{% endif %}
</div>
</nav>
<div class="container">
{% for msg in get_flashed_messages() %}
<div class="flash">{{ msg }}</div>
{% endfor %}
{{ content|safe }}
</div>
<footer>DevConnect © 2026 — Conectando ideias e desenvolvedores.</footer>
</body>
</html>
"""


def page(title, content, **kwargs):
    return render_template_string(
        BASE,
        title=title,
        content=render_template_string(content, **kwargs),
        user=current_user()
    )


@app.route("/")
def home():
    user = current_user()
    conn = db()
    projects = conn.execute(
        """SELECT projects.*, users.name
           FROM projects JOIN users ON users.id=projects.user_id
           WHERE status='Aberto' ORDER BY projects.id DESC LIMIT 6"""
    ).fetchall()
    developers = conn.execute(
        "SELECT * FROM users WHERE role='developer' ORDER BY id DESC LIMIT 4"
    ).fetchall()
    conn.close()

    return page("Início", """
    <div class="card">
      <h1>Encontre o desenvolvedor ideal para sua ideia.</h1>
      <p>Publique seu projeto, receba propostas e encontre profissionais para transformar sua ideia em realidade.</p>
      {% if not user %}
      <a class="btn" href="{{ url_for('register') }}">Começar gratuitamente</a>
      {% else %}
      <a class="btn" href="{{ url_for('projects') }}">Explorar projetos</a>
      {% endif %}
    </div>

    <h2>Projetos recentes</h2>
    <div class="grid">
    {% for p in projects %}
      <div class="card">
        <h3>{{ p.title }}</h3>
        <p>{{ p.description[:120] }}</p>
        <small>Publicado por {{ p.name }}</small><br><br>
        <a href="{{ url_for('project_detail', project_id=p.id) }}">Ver projeto →</a>
      </div>
    {% else %}
      <p>Nenhum projeto publicado ainda.</p>
    {% endfor %}
    </div>

    <h2>Desenvolvedores</h2>
    <div class="grid">
    {% for d in developers %}
      <div class="card">
        <h3>{{ d.name }}</h3>
        <p>{{ d.bio or 'Desenvolvedor na DevConnect.' }}</p>
        <span class="tag">{{ d.skills or 'Desenvolvimento web' }}</span>
      </div>
    {% endfor %}
    </div>
    """, projects=projects, developers=developers, user=user)


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        role = request.form.get("role", "")
        
        if not name or not email or len(password) < 6:
            flash("Preencha os campos. A senha precisa ter pelo menos 6 caracteres.")
            return redirect(url_for("register"))

        if role not in ("client", "developer"):
            flash("Selecione um tipo de conta válido.")
            return redirect(url_for("register"))

        conn = db()
        try:
            conn.execute(
                "INSERT INTO users(name,email,password,role) VALUES(?,?,?,?)",
                (name, email, generate_password_hash(password), role)
            )
            conn.commit()
            flash("Conta criada! Agora faça login.")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("Este email já está cadastrado.")
        finally:
            conn.close()

    return page("Cadastro", """
    <div class="card">
    <h1>Criar conta</h1>
    <p>Cadastre-se gratuitamente.</p>
    <form method="POST">
      <label>Nome</label>
      <input name="name" required placeholder="Seu nome">
      <label>Email</label>
      <input name="email" type="email" required placeholder="seu@email.com">
      <label>Senha</label>
      <input name="password" type="password" required minlength="6">
      <label>Quero me cadastrar como:</label>
      <select name="role" required>
        <option value="client">Cliente — preciso de um site</option>
        <option value="developer">Desenvolvedor — quero encontrar projetos</option>
      </select>
      <button type="submit">Criar minha conta grátis</button>
    </form>
    </div>
    """)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        conn = db()
        user = conn.execute(
            "SELECT * FROM users WHERE email=?", (email,)
        ).fetchone()
        conn.close()

        if user and check_password_hash(user["password"], password):
            session.clear()
            session["user_id"] = user["id"]
            flash("Bem-vindo ao DevConnect!")
            return redirect(url_for("home"))

        flash("Email ou senha incorretos.")

    return page("Login", """
    <div class="card">
    <h1>Entrar na conta</h1>
    <form method="POST">
      <label>Email</label>
      <input name="email" type="email" required>
      <label>Senha</label>
      <input name="password" type="password" required>
      <button>Entrar</button>
    </form>
    <p>Não tem conta? <a href="{{ url_for('register') }}">Cadastre-se</a></p>
    </div>
    """)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))


@app.route("/projects")
def projects():
    conn = db()
    items = conn.execute("""
        SELECT projects.*, users.name
        FROM projects JOIN users ON users.id=projects.user_id
        WHERE projects.status='Aberto'
        ORDER BY projects.id DESC
    """).fetchall()
    conn.close()

    return page("Projetos", """
    <h1>Projetos disponíveis</h1>
    {% if user and user.role == 'client' %}
    <a class="btn" href="{{ url_for('new_project') }}">+ Publicar projeto</a>
    {% endif %}
    {% for p in items %}
    <div class="card">
      <h2>{{ p.title }}</h2>
      <p>{{ p.description }}</p>
      <small>Cliente: {{ p.name }} | Orçamento: {{ p.budget or 'A combinar' }}</small><br><br>
      <a href="{{ url_for('project_detail', project_id=p.id) }}">Ver detalhes →</a>
    </div>
    {% else %}
    <p>Nenhum projeto disponível.</p>
    {% endfor %}
    """, items=items)


@app.route("/project/new", methods=["GET", "POST"])
@login_required
def new_project():
    user = current_user()
    if user["role"] != "client":
        flash("Somente clientes podem publicar projetos.")
        return redirect(url_for("projects"))

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        budget = request.form.get("budget", "").strip()

        if title and description:
            conn = db()
            conn.execute(
                "INSERT INTO projects(user_id,title,description,budget) VALUES(?,?,?,?)",
                (user["id"], title, description, budget)
            )
            conn.commit()
            conn.close()
            flash("Projeto publicado gratuitamente!")
            return redirect(url_for("projects"))

    return page("Novo projeto", """
    <div class="card">
    <h1>Publicar projeto</h1>
    <form method="POST">
      <label>Nome do projeto</label>
      <input name="title" required placeholder="Ex: Criar loja virtual">
      <label>Descreva o que você precisa</label>
      <textarea name="description" required placeholder="Explique como deseja seu site..."></textarea>
      <label>Orçamento (opcional)</label>
      <input name="budget" placeholder="Ex: R$ 500 ou a combinar">
      <button>Publicar gratuitamente</button>
    </form>
    </div>
    """)


@app.route("/project/<int:project_id>", methods=["GET", "POST"])
def project_detail(project_id):
    conn = db()
    project = conn.execute("""
        SELECT projects.*, users.name, users.id AS owner_id
        FROM projects JOIN users ON users.id=projects.user_id
        WHERE projects.id=?
    """, (project_id,)).fetchone()

    if not project:
        conn.close()
        return "Projeto não encontrado", 404

    user = current_user()

    if request.method == "POST":
        if not user:
            conn.close()
            return redirect(url_for("login"))

        if user["role"] != "developer":
            flash("Somente desenvolvedores podem enviar propostas.")
        elif user["id"] == project["owner_id"]:
            flash("Você não pode enviar proposta para seu próprio projeto.")
        else:
            message = request.form.get("message", "").strip()
            price = request.form.get("price", "").strip()
            if message:
                try:
                    conn.execute(
                        "INSERT INTO proposals(project_id,developer_id,message,price) VALUES(?,?,?,?)",
                        (project_id, user["id"], message, price)
                    )
                    conn.commit()
                    flash("Proposta enviada gratuitamente!")
                except sqlite3.IntegrityError:
                    flash("Você já enviou uma proposta para este projeto.")

    proposals = conn.execute("""
        SELECT proposals.*, users.name, users.skills
        FROM proposals JOIN users ON users.id=proposals.developer_id
        WHERE project_id=?
        ORDER BY proposals.id DESC
    """, (project_id,)).fetchall()

    conn.close()

    return page("Detalhes do projeto", """
    <div class="card">
      <h1>{{ project.title }}</h1>
      <p>{{ project.description }}</p>
      <p>Cliente: {{ project.name }}</p>
      <p>Orçamento: {{ project.budget or 'A combinar' }}</p>
    </div>

    {% if user and user.role == 'developer' %}
    <div class="card">
      <h2>Enviar proposta</h2>
      <form method="POST">
        <textarea name="message" required placeholder="Explique como você pode desenvolver este projeto"></textarea>
        <input name="price" placeholder="Seu orçamento (opcional)">
        <button>Enviar proposta grátis</button>
      </form>
    </div>
    {% endif %}

    <h2>Propostas recebidas</h2>
    {% if user and user.id == project.owner_id %}
      {% for p in proposals %}
      <div class="card">
        <h3>{{ p.name }}</h3>
        <p>{{ p.message }}</p>
        <p>Orçamento: {{ p.price or 'A combinar' }}</p>
        <a href="{{ url_for('chat', receiver_id=p.developer_id) }}">Conversar com desenvolvedor</a>
      </div>
      {% else %}
      <p>Ainda não há propostas.</p>
      {% endfor %}
    {% else %}
      <p>As propostas são visíveis somente ao cliente que publicou o projeto.</p>
    {% endif %}
    """, project=project, proposals=proposals, user=user)


@app.route("/developers")
def developers():
    conn = db()
    items = conn.execute(
        "SELECT * FROM users WHERE role='developer' ORDER BY id DESC"
    ).fetchall()
    conn.close()

    return page("Desenvolvedores", """
    <h1>Encontre profissionais</h1>
    <div class="grid">
    {% for d in items %}
      <div class="card">
        <h2>{{ d.name }}</h2>
        <p>{{ d.bio or 'Desenvolvedor disponível para projetos.' }}</p>
        <span class="tag">{{ d.skills or 'Desenvolvimento web' }}</span>
        {% if user and user.role == 'client' %}
        <p><a href="{{ url_for('chat', receiver_id=d.id) }}">Enviar mensagem →</a></p>
        {% endif %}
      </div>
    {% else %}
      <p>Nenhum desenvolvedor cadastrado.</p>
    {% endfor %}
    </div>
    """, items=items)


@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    user = current_user()

    if request.method == "POST":
        conn = db()
        conn.execute(
            "UPDATE users SET bio=?, skills=? WHERE id=?",
            (
                request.form.get("bio", "")[:1000],
                request.form.get("skills", "")[:300],
                user["id"]
            )
        )
        conn.commit()
        conn.close()
        flash("Perfil atualizado!")
        return redirect(url_for("profile"))

    return page("Meu perfil", """
    <div class="card">
    <h1>Meu perfil</h1>
    <p>{{ user.name }} — {{ 'Desenvolvedor' if user.role == 'developer' else 'Cliente' }}</p>
    <form method="POST">
      <label>Sobre você</label>
      <textarea name="bio">{{ user.bio }}</textarea>
      <label>Especialidades</label>
      <input name="skills" value="{{ user.skills }}" placeholder="HTML, CSS, Python, Flask...">
      <button>Salvar perfil</button>
    </form>
    </div>
    """, user=user)


@app.route("/chat/<int:receiver_id>", methods=["GET", "POST"])
@login_required
def chat(receiver_id):
    user = current_user()
    conn = db()
    receiver = conn.execute(
        "SELECT * FROM users WHERE id=?", (receiver_id,)
    ).fetchone()

    if not receiver or receiver_id == user["id"]:
        conn.close()
        return "Usuário inválido.", 404

    # Só permite conversas entre cliente e desenvolvedor.
    if receiver["role"] == user["role"]:
        conn.close()
        return "Conversa não permitida.", 403

    if request.method == "POST":
        message = request.form.get("message", "").strip()
        if message:
            conn.execute(
                "INSERT INTO messages(sender_id,receiver_id,message) VALUES(?,?,?)",
                (user["id"], receiver_id, message)
            )
            conn.commit()

    messages = conn.execute("""
        SELECT * FROM messages
        WHERE (sender_id=? AND receiver_id=?)
        OR (sender_id=? AND receiver_id=?)
        ORDER BY id ASC
    """, (user["id"], receiver_id, receiver_id, user["id"])).fetchall()

    conn.close()

    return page("Conversa", """
    <div class="card">
      <h2>Conversa com {{ receiver.name }}</h2>
      {% for m in messages %}
      <div class="card">
        <small>{{ 'Você' if m.sender_id == user.id else receiver.name }}</small>
        <p>{{ m.message }}</p>
        <small>{{ m.created_at }}</small>
      </div>
      {% else %}
      <p>Comece a conversa!</p>
      {% endfor %}
      <form method="POST">
        <textarea name="message" required placeholder="Digite sua mensagem..."></textarea>
        <button>Enviar mensagem</button>
      </form>
    </div>
    """, receiver=receiver, messages=messages, user=user)


@app.route("/inbox")
@login_required
def inbox():
    user = current_user()
    conn = db()
    rows = conn.execute("""
        SELECT users.id, users.name, MAX(messages.id) AS last_id
        FROM messages
        JOIN users ON users.id =
          CASE WHEN messages.sender_id=? THEN messages.receiver_id
               ELSE messages.sender_id END
        WHERE messages.sender_id=? OR messages.receiver_id=?
        GROUP BY users.id
        ORDER BY last_id DESC
    """, (user["id"], user["id"], user["id"])).fetchall()
    conn.close()

    return page("Mensagens", """
    <h1>Minhas conversas</h1>
    {% for r in rows %}
    <div class="card">
      <h3>{{ r.name }}</h3>
      <a href="{{ url_for('chat', receiver_id=r.id) }}">Abrir conversa →</a>
    </div>
    {% else %}
    <p>Você ainda não possui conversas.</p>
    {% endfor %}
    """, rows=rows)


@app.route("/review/<int:developer_id>", methods=["GET", "POST"])
@login_required
def review(developer_id):
    user = current_user()
    if user["role"] != "client":
        return "Somente clientes podem avaliar.", 403

    conn = db()
    developer = conn.execute(
        "SELECT * FROM users WHERE id=? AND role='developer'",
        (developer_id,)
    ).fetchone()

    if not developer:
        conn.close()
        return "Desenvolvedor não encontrado.", 404

    if request.method == "POST":
        rating = request.form.get("rating", type=int)
        comment = request.form.get("comment", "").strip()

        if rating not in range(1, 6):
            flash("Escolha uma nota entre 1 e 5.")
        else:
            conn.execute(
                "INSERT INTO reviews(reviewer_id,developer_id,rating,comment) VALUES(?,?,?,?)",
                (user["id"], developer_id, rating, comment)
            )
            conn.commit()
            flash("Avaliação enviada!")
            conn.close()
            return redirect(url_for("developers"))

    conn.close()

    return page("Avaliar desenvolvedor", """
    <div class="card">
    <h1>Avaliar {{ developer.name }}</h1>
    <form method="POST">
      <label>Nota</label>
      <select name="rating">
        <option value="5">5 - Excelente</option>
        <option value="4">4 - Muito bom</option>
        <option value="3">3 - Bom</option>
        <option value="2">2 - Regular</option>
        <option value="1">1 - Ruim</option>
      </select>
      <label>Comentário</label>
      <textarea name="comment"></textarea>
      <button>Enviar avaliação</button>
    </form>
    </div>
    """, developer=developer)


@app.route("/admin")
@login_required
def admin():
    # Não existe administrador público ou senha universal.
    if not session.get("is_admin"):
        return "Acesso restrito.", 403

    conn = db()
    users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    projects = conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
    conn.close()

    return page("Administração", """
    <h1>Painel administrativo</h1>
    <div class="grid">
      <div class="card"><h2>{{ users }}</h2><p>Usuários cadastrados</p></div>
      <div class="card"><h2>{{ projects }}</h2><p>Projetos publicados</p></div>
    </div>
    """, users=users, projects=projects)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
