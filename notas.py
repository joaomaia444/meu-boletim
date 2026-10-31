
import os
import sqlite3
from pathlib import Path
from functools import wraps

from flask import (
    Flask, request, redirect, session,
    flash, render_template_string
)
from werkzeug.security import generate_password_hash, check_password_hash
from markupsafe import escape

app = Flask(__name__)

# CONFIGURAÇÕES
app.secret_key = os.environ.get(
    "SECRET_KEY", "troque-esta-chave-por-uma-chave-secreta"
)

BASE_DIR = Path(__file__).resolve().parent
BANCO = BASE_DIR / "boletim.db"

CHAVE_PIX = os.environ.get("CHAVE_PIX", "COLOQUE_SUA_CHAVE_PIX")
NOME_PIX = os.environ.get("NOME_PIX", "SEU NOME")
VALOR = "10,00"

SENHA_ADMIN = os.environ.get("SENHA_ADMIN", "Jotta@123")


# --------------------------------------------------
# BANCO DE DADOS
# --------------------------------------------------

def conectar():
    banco = sqlite3.connect(str(BANCO), timeout=30)
    banco.row_factory = sqlite3.Row
    return banco


def criar_banco():
    with conectar() as banco:
        banco.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                senha TEXT NOT NULL,
                status TEXT DEFAULT 'pendente',
                comprovante TEXT
            )
        """)


# IMPORTANTE: executa também quando o Gunicorn inicia o app no Render.
criar_banco()


# --------------------------------------------------
# USUÁRIO E PROTEÇÃO DE PÁGINAS
# --------------------------------------------------

def usuario_atual():
    usuario_id = session.get("usuario")

    if not usuario_id:
        return None

    with conectar() as banco:
        return banco.execute(
            "SELECT * FROM usuarios WHERE id = ?",
            (usuario_id,)
        ).fetchone()


def proteger(funcao):
    @wraps(funcao)
    def verificar(*args, **kwargs):
        if not usuario_atual():
            return redirect("/login")
        return funcao(*args, **kwargs)
    return verificar


def liberar(funcao):
    @wraps(funcao)
    def verificar(*args, **kwargs):
        usuario = usuario_atual()

        if not usuario:
            return redirect("/login")

        if usuario["status"] != "aprovado":
            return redirect("/pagamento")

        return funcao(*args, **kwargs)
    return verificar


# --------------------------------------------------
# VISUAL DO SITE
# --------------------------------------------------

def pagina(titulo, conteudo):
    usuario = usuario_atual()

    menu = """
        <a href="/">Início</a>
        <a href="/criar-conta">Criar conta</a>
        <a href="/login">Login</a>
    """

    if usuario:
        menu = """
            <a href="/boletim">Meu boletim</a>
            <a href="/pagamento">Pagamento</a>
            <a href="/sair">Sair</a>
        """

    return render_template_string("""
    <!DOCTYPE html>
    <html lang="pt-br">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>{{ titulo }} - Meu Boletim</title>

        <style>
            * { box-sizing: border-box; }

            body {
                margin: 0;
                background: #f1f4fa;
                font-family: Arial, sans-serif;
                color: #18233a;
            }

            header {
                background: #101b35;
                color: white;
                padding: 22px 8%;
                display: flex;
                justify-content: space-between;
                align-items: center;
                flex-wrap: wrap;
                gap: 15px;
            }

            header strong { font-size: 22px; }

            header a {
                color: white;
                text-decoration: none;
                margin-left: 15px;
            }

            main {
                max-width: 850px;
                margin: 50px auto;
                padding: 0 18px;
            }

            .card {
                background: white;
                padding: 35px;
                border-radius: 18px;
                box-shadow: 0 8px 30px #00000010;
            }

            h1 { font-size: 30px; }

            p {
                color: #647087;
                line-height: 1.6;
            }

            input, textarea {
                width: 100%;
                padding: 14px;
                border: 1px solid #d9dfeb;
                border-radius: 9px;
                margin: 8px 0 18px;
                font-size: 15px;
            }

            label { font-weight: bold; }

            button, .botao {
                display: inline-block;
                background: #315efb;
                color: white;
                padding: 14px 20px;
                border: none;
                border-radius: 9px;
                text-decoration: none;
                cursor: pointer;
                font-weight: bold;
            }

            .botao-secundario {
                background: #101b35;
            }

            .pix {
                background: #f0f3ff;
                padding: 18px;
                border-radius: 12px;
                overflow-wrap: anywhere;
            }

            .mensagem {
                background: #fff1c9;
                padding: 13px;
                border-radius: 9px;
                margin-bottom: 15px;
            }

            table {
                width: 100%;
                border-collapse: collapse;
            }

            td, th {
                padding: 10px;
                border-bottom: 1px solid #ddd;
                text-align: left;
            }

            @media(max-width: 600px) {
                header { padding: 20px; }
                header a { margin-left: 5px; }
                .card { padding: 22px; }
                h1 { font-size: 25px; }
            }
        </style>
    </head>

    <body>
        <header>
            <strong>MEU BOLETIM</strong>
            <nav>{{ menu|safe }}</nav>
        </header>

        <main>
            {% for mensagem in get_flashed_messages() %}
                <div class="mensagem">{{ mensagem }}</div>
            {% endfor %}

            {{ conteudo|safe }}
        </main>
    </body>
    </html>
    """, titulo=titulo, conteudo=conteudo, menu=menu)


# --------------------------------------------------
# PÁGINA INICIAL
# --------------------------------------------------

@app.route("/")
def inicio():
    return pagina("Início", """
        <div class="card">
            <h1>Bem-vindo ao Meu Boletim!</h1>

            <p>
                Organize suas notas escolares em um só lugar.
                Acompanhe seu desempenho durante o ano letivo.
            </p>

            <a class="botao" href="/criar-conta">CRIAR CONTA</a>
            <a class="botao botao-secundario" href="/login">
                FAZER LOGIN
            </a>
        </div>
    """)


# --------------------------------------------------
# CADASTRO
# --------------------------------------------------

@app.route("/criar-conta", methods=["GET", "POST"])
def criar_conta():

    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        email = request.form.get("email", "").strip().lower()
        senha = request.form.get("senha", "")

        if not nome or not email or len(senha) < 6:
            flash("Preencha todos os campos. A senha precisa ter pelo menos 6 caracteres.")
            return redirect("/criar-conta")

        try:
            with conectar() as banco:
                cursor = banco.execute("""
                    INSERT INTO usuarios (nome, email, senha)
                    VALUES (?, ?, ?)
                """, (
                    nome,
                    email,
                    generate_password_hash(senha)
                ))

                novo_id = cursor.lastrowid

            session["usuario"] = novo_id
            return redirect("/pagamento")

        except sqlite3.IntegrityError:
            flash("Este e-mail já está cadastrado.")
            return redirect("/criar-conta")

        except sqlite3.Error:
            app.logger.exception("Erro ao cadastrar usuário")
            flash("Não foi possível realizar o cadastro. Tente novamente.")
            return redirect("/criar-conta")

    return pagina("Criar conta", """
        <div class="card">
            <h1>Criar minha conta</h1>

            <form method="POST">
                <label>Nome completo</label>
                <input name="nome" required maxlength="120">

                <label>E-mail</label>
                <input name="email" type="email" required>

                <label>Senha</label>
                <input name="senha" type="password"
                       minlength="6" required>

                <button type="submit">CADASTRAR E CONTINUAR</button>
            </form>

            <p>Já possui conta? <a href="/login">Entre aqui</a>.</p>
        </div>
    """)


# --------------------------------------------------
# LOGIN
# --------------------------------------------------

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        senha = request.form.get("senha", "")

        with conectar() as banco:
            usuario = banco.execute(
                "SELECT * FROM usuarios WHERE email = ?",
                (email,)
            ).fetchone()

        if usuario and check_password_hash(usuario["senha"], senha):
            session.clear()
            session["usuario"] = usuario["id"]

            if usuario["status"] == "aprovado":
                return redirect("/boletim")

            return redirect("/pagamento")

        flash("E-mail ou senha incorretos.")

    return pagina("Login", """
        <div class="card">
            <h1>Entrar na minha conta</h1>

            <form method="POST">
                <label>E-mail</label>
                <input name="email" type="email" required>

                <label>Senha</label>
                <input name="senha" type="password" required>

                <button type="submit">ENTRAR</button>
            </form>

            <p>Não tem conta? <a href="/criar-conta">Cadastre-se</a>.</p>
        </div>
    """)


# --------------------------------------------------
# PAGAMENTO
# --------------------------------------------------

@app.route("/pagamento", methods=["GET", "POST"])
@proteger
def pagamento():

    usuario = usuario_atual()

    if usuario["status"] == "aprovado":
        return redirect("/boletim")

    if request.method == "POST":
        comprovante = request.form.get("comprovante", "").strip()

        if not comprovante:
            flash("Informe os dados do comprovante.")
            return redirect("/pagamento")

        with conectar() as banco:
            banco.execute("""
                UPDATE usuarios
                SET comprovante = ?, status = 'em análise'
                WHERE id = ?
            """, (comprovante, usuario["id"]))

        flash("Comprovante enviado! Aguarde a aprovação.")
        return redirect("/pagamento")

    return pagina("Pagamento", f"""
        <div class="card">
            <h1>Pagamento</h1>

            <p>
                Para solicitar a liberação do acesso,
                realize o pagamento via Pix.
            </p>

            <div class="pix">
                <h2>R$ {VALOR}</h2>

                <p><strong>Chave Pix:</strong>
                {escape(CHAVE_PIX)}</p>

                <p><strong>Recebedor:</strong>
                {escape(NOME_PIX)}</p>
            </div>

            <p>Status: <strong>{escape(usuario["status"])}</strong></p>

            <form method="POST">
                <label>Comprovante ou identificação do pagamento</label>

                <textarea name="comprovante" required
                    placeholder="Informe os dados ou link do comprovante"
                ></textarea>

                <button type="submit">ENVIAR COMPROVANTE</button>
            </form>

            <p>
                O administrador verificará o recebimento antes
                de liberar sua conta.
            </p>
        </div>
    """)


# --------------------------------------------------
# BOLETIM
# --------------------------------------------------

@app.route("/boletim")
@liberar
def boletim():

    usuario = usuario_atual()

    return pagina("Meu boletim", f"""
        <div class="card">
            <h1>Olá, {escape(usuario["nome"])}!</h1>

            <p>Sua conta foi aprovada.</p>

            <h2>Meu boletim escolar</h2>

            <p>
                Seu acesso está liberado.
                Aqui ficará seu controle de notas.
            </p>
        </div>
    """)


# --------------------------------------------------
# SAIR DA CONTA
# --------------------------------------------------

@app.route("/sair")
def sair():
    session.clear()
    return redirect("/")


# --------------------------------------------------
# ADMINISTRADOR
# --------------------------------------------------

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():

    if request.method == "POST":
        senha = request.form.get("senha", "")

        if senha == SENHA_ADMIN:
            session["admin"] = True
            return redirect("/admin")

        flash("Senha incorreta.")

    return pagina("Administração", """
        <div class="card">
            <h1>Área administrativa</h1>

            <form method="POST">
                <label>Senha do administrador</label>
                <input name="senha" type="password" required>

                <button type="submit">ENTRAR</button>
            </form>
        </div>
    """)


@app.route("/admin")
def admin():

    if not session.get("admin"):
        return redirect("/admin/login")

    with conectar() as banco:
        usuarios = banco.execute(
            "SELECT * FROM usuarios ORDER BY id DESC"
        ).fetchall()

    linhas = ""

    for usuario in usuarios:
        comprovante = escape(
            usuario["comprovante"] or "Não enviado"
        )

        acao = ""

        if usuario["status"] != "aprovado":
            acao = f"""
                <form method="POST"
                      action="/admin/aprovar/{usuario['id']}">
                    <button type="submit">Aprovar conta</button>
                </form>
            """

        linhas += f"""
            <tr>
                <td>{escape(usuario["nome"])}</td>
                <td>{escape(usuario["email"])}</td>
                <td>{escape(usuario["status"])}</td>
                <td>{comprovante}</td>
                <td>{acao}</td>
            </tr>
        """

    return pagina("Administração", f"""
        <div class="card">
            <h1>Gerenciar pagamentos</h1>

            <p>
                Confira o recebimento no banco antes de aprovar
                qualquer conta.
            </p>

            <div style="overflow-x:auto">
                <table>
                    <tr>
                        <th>Nome</th>
                        <th>E-mail</th>
                        <th>Status</th>
                        <th>Comprovante</th>
                        <th>Ação</th>
                    </tr>

                    {linhas}
                </table>
            </div>

            <p><a href="/admin/sair">Sair da administração</a></p>
        </div>
    """)


@app.route("/admin/aprovar/<int:id>", methods=["POST"])
def aprovar(id):

    if not session.get("admin"):
        return redirect("/admin/login")

    with conectar() as banco:
        banco.execute(
            "UPDATE usuarios SET status = 'aprovado' WHERE id = ?",
            (id,)
        )

    flash("Conta aprovada.")
    return redirect("/admin")


@app.route("/admin/sair")
def admin_sair():
    session.pop("admin", None)
    return redirect("/admin/login")


# --------------------------------------------------
# VERIFICAÇÃO DO SERVIDOR
# --------------------------------------------------

@app.route("/health")
def health():
    try:
        with conectar() as banco:
            banco.execute("SELECT 1")

        return {"status": "ok", "banco": "conectado"}, 200

    except sqlite3.Error:
        app.logger.exception("Erro na verificação do banco")
        return {"status": "erro", "banco": "indisponível"}, 500


# --------------------------------------------------
# INICIAR LOCALMENTE
# --------------------------------------------------

if __name__ == "__main__":
    app.run(debug=False)
