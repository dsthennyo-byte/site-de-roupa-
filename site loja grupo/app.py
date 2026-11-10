import os
import secrets
import math

from flask import Flask, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from banco import (
    alternar_status_produto,
    atualizar_produto,
    buscar_produto,
    buscar_usuario_por_email,
    buscar_usuario_por_id,
    criar_banco,
    criar_usuario,
    excluir_produto,
    finalizar_pedido,
    inserir_produto,
    listar_pedidos_usuario,
    listar_produtos,
)

IMAGENS_PRODUTO = {
    "alfaiataria.jpg": "Alfaiataria",
    "acessorios.jpg": "Acessórios",
    "vestido.jpg": "Moda feminina",
    "calcados.jpg": "Calçados",
    "jeans.jpg": "Jeans",
    "editorial.jpg": "Editorial",
}

app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    TEMPLATES_AUTO_RELOAD=True,
)

criar_banco()


def usuario_atual():
    id_usuario = session.get("usuario_id")
    return buscar_usuario_por_id(id_usuario) if id_usuario else None


def itens_carrinho():
    carrinho = session.get("carrinho", {})
    linhas = []
    total = 0
    quantidade_total = 0

    for id_produto, quantidade in carrinho.items():
        produto = buscar_produto(int(id_produto))
        if produto is None:
            continue
        subtotal = produto["preco"] * quantidade
        linhas.append({"produto": produto, "quantidade": quantidade, "subtotal": subtotal})
        total += subtotal
        quantidade_total += quantidade

    return linhas, total, quantidade_total


@app.route("/")
def index():
    linhas, total, quantidade_total = itens_carrinho()
    return render_template(
        "index.html",
        produtos=listar_produtos(),
        carrinho=linhas,
        total=total,
        quantidade_total=quantidade_total,
        usuario=usuario_atual(),
    )


@app.route("/registrar", methods=["GET", "POST"])
def registrar():
    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        email = request.form.get("email", "").strip().lower()
        senha = request.form.get("senha", "")

        if not nome or "@" not in email or len(senha) < 8:
            flash("Informe nome, e-mail válido e uma senha com pelo menos 8 caracteres.", "erro")
        elif buscar_usuario_por_email(email):
            flash("Este e-mail já está cadastrado. Faça login para continuar.", "erro")
        else:
            id_usuario = criar_usuario(nome, email, generate_password_hash(senha))
            session["usuario_id"] = id_usuario
            flash("Sua conta foi criada. Boas-vindas à Yan Sthennyo Jeans!", "sucesso")
            return redirect(url_for("index"))

    return render_template("index.html", modo="registrar", usuario=usuario_atual())


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        senha = request.form.get("senha", "")
        usuario = buscar_usuario_por_email(email)
        if usuario is None or not check_password_hash(usuario["senha_hash"], senha):
            flash("E-mail ou senha incorretos.", "erro")
        else:
            carrinho = session.get("carrinho", {})
            session.clear()
            session["usuario_id"] = usuario["id"]
            session["carrinho"] = carrinho
            flash("Login realizado com sucesso.", "sucesso")
            return redirect(url_for("index"))

    return render_template("index.html", modo="login", usuario=usuario_atual())


@app.route("/sair", methods=["POST"])
def sair():
    session.clear()
    flash("Você saiu da sua conta.", "sucesso")
    return redirect(url_for("index"))


@app.route("/carrinho/adicionar/<int:id_produto>", methods=["POST"])
def adicionar_carrinho(id_produto):
    produto = buscar_produto(id_produto)
    if produto is None or produto["status"] != "Disponível":
        flash("Este produto não está disponível.", "erro")
        return redirect(url_for("index"))

    try:
        quantidade = int(request.form.get("quantidade", "1"))
    except ValueError:
        quantidade = 0
    carrinho = session.get("carrinho", {})
    id_texto = str(id_produto)
    nova_quantidade = carrinho.get(id_texto, 0) + quantidade
    if quantidade < 1:
        flash("Escolha uma quantidade válida.", "erro")
    elif nova_quantidade > produto["quantidade"]:
        flash(f"Temos apenas {produto['quantidade']} unidade(s) em estoque.", "erro")
    else:
        carrinho[id_texto] = nova_quantidade
        session["carrinho"] = carrinho
        flash(f"{produto['nome']} foi adicionado ao carrinho.", "sucesso")
    return redirect(url_for("index"))


@app.route("/carrinho/atualizar", methods=["POST"])
def atualizar_carrinho():
    carrinho = session.get("carrinho", {})
    novo_carrinho = {}
    for id_texto in carrinho:
        try:
            quantidade = int(request.form.get(f"quantidade_{id_texto}", "0"))
            produto = buscar_produto(int(id_texto))
        except ValueError:
            continue
        if quantidade > 0 and produto and quantidade <= produto["quantidade"]:
            novo_carrinho[id_texto] = quantidade
    session["carrinho"] = novo_carrinho
    flash("Carrinho atualizado.", "sucesso")
    return redirect(url_for("index") + "#carrinho")


@app.route("/carrinho/remover/<int:id_produto>", methods=["POST"])
def remover_carrinho(id_produto):
    carrinho = session.get("carrinho", {})
    carrinho.pop(str(id_produto), None)
    session["carrinho"] = carrinho
    flash("Produto removido do carrinho.", "sucesso")
    return redirect(url_for("index") + "#carrinho")


@app.route("/finalizar", methods=["POST"])
def finalizar():
    usuario = usuario_atual()
    carrinho = session.get("carrinho", {})
    if usuario is None:
        flash("Entre na sua conta para finalizar o pedido.", "erro")
        return redirect(url_for("login"))
    if not carrinho:
        flash("Seu carrinho está vazio.", "erro")
        return redirect(url_for("index") + "#carrinho")

    try:
        itens = {int(id_produto): int(quantidade) for id_produto, quantidade in carrinho.items()}
        id_pedido = finalizar_pedido(usuario["id"], itens)
    except ValueError as erro:
        flash(str(erro), "erro")
        return redirect(url_for("index") + "#carrinho")

    session["carrinho"] = {}
    flash(
        f"Pedido #{id_pedido} registrado. Pagamento e envio ainda precisam ser combinados com a loja.",
        "sucesso",
    )
    return redirect(url_for("pedidos"))


@app.route("/pedidos")
def pedidos():
    usuario = usuario_atual()
    if usuario is None:
        flash("Entre na sua conta para consultar seus pedidos.", "erro")
        return redirect(url_for("login"))
    return render_template(
        "index.html",
        modo="pedidos",
        usuario=usuario,
        pedidos=listar_pedidos_usuario(usuario["id"]),
        produtos=listar_produtos(),
    )


def ler_dados_produto():
    nome = request.form.get("nome", "").strip()
    categoria = request.form.get("categoria", "").strip()
    descricao = request.form.get("descricao", "").strip()
    imagem = request.form.get("imagem", "")
    try:
        preco = float(request.form.get("preco", "").replace(",", "."))
        quantidade = int(request.form.get("quantidade", "0"))
    except ValueError:
        return None

    if (
        not nome
        or not categoria
        or imagem not in IMAGENS_PRODUTO
        or not math.isfinite(preco)
        or preco < 0
        or quantidade < 0
    ):
        return None
    status_produto = request.form.get("status", "Disponível")
    if status_produto not in ("Disponível", "Indisponível"):
        return None
    return nome, categoria, descricao, preco, quantidade, status_produto, imagem


@app.route("/cadastrar", methods=["GET", "POST"])
def cadastrar():
    if request.method == "POST":
        dados = ler_dados_produto()
        if dados:
            inserir_produto(*dados)
            flash("Produto cadastrado com sucesso.", "sucesso")
            return redirect(url_for("index"))
        flash("Confira os dados, o preço e a quantidade informados.", "erro")
    return render_template(
        "produto_form.html",
        titulo="Cadastrar produto",
        imagens=IMAGENS_PRODUTO,
    )


@app.route("/editar/<int:id_produto>", methods=["GET", "POST"])
def editar(id_produto):
    produto = buscar_produto(id_produto)
    if produto is None:
        flash("Produto não encontrado.", "erro")
        return redirect(url_for("index"))

    if request.method == "POST":
        dados = ler_dados_produto()
        if dados:
            atualizar_produto(id_produto, *dados)
            flash("Produto atualizado com sucesso.", "sucesso")
            return redirect(url_for("index"))
        flash("Confira os dados, o preço e a quantidade informados.", "erro")
    return render_template(
        "produto_form.html",
        titulo="Editar produto",
        produto=produto,
        imagens=IMAGENS_PRODUTO,
    )


@app.route("/status/<int:id_produto>", methods=["POST"])
def status(id_produto):
    alternar_status_produto(id_produto)
    return redirect(url_for("index"))


@app.route("/excluir/<int:id_produto>", methods=["POST"])
def excluir(id_produto):
    excluir_produto(id_produto)
    flash("Produto excluído.", "sucesso")
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")
