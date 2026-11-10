import sqlite3
from contextlib import contextmanager
import os
from pathlib import Path

CAMINHO_BANCO = Path(
    os.environ.get("DATABASE_PATH", Path(__file__).with_name("produtos.db"))
)


@contextmanager
def conectar():
    conexao = sqlite3.connect(CAMINHO_BANCO)
    conexao.row_factory = sqlite3.Row
    try:
        yield conexao
        conexao.commit()
    except Exception:
        conexao.rollback()
        raise
    finally:
        conexao.close()


def criar_banco():
    with conectar() as conexao:
        conexao.execute(
            """
            CREATE TABLE IF NOT EXISTS produtos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                categoria TEXT NOT NULL,
                descricao TEXT,
                preco REAL NOT NULL,
                quantidade INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'Disponível',
                imagem TEXT NOT NULL DEFAULT 'editorial.jpg'
            );
            """
        )
        colunas_produtos = {
            coluna["name"]
            for coluna in conexao.execute("PRAGMA table_info(produtos)")
        }
        if "imagem" not in colunas_produtos:
            conexao.execute(
                "ALTER TABLE produtos ADD COLUMN imagem TEXT NOT NULL DEFAULT 'editorial.jpg'"
            )
            conexao.execute(
                """
                UPDATE produtos
                SET imagem = CASE nome
                    WHEN 'Blazer Atelier' THEN 'alfaiataria.jpg'
                    WHEN 'Bolsa Signature' THEN 'acessorios.jpg'
                    WHEN 'Vestido Lumière' THEN 'vestido.jpg'
                    WHEN 'Tênis Urban Lux' THEN 'calcados.jpg'
                    ELSE 'editorial.jpg'
                END
                """
            )
        conexao.execute(
            """
            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                senha_hash TEXT NOT NULL,
                criado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        conexao.execute(
            """
            CREATE TABLE IF NOT EXISTS pedidos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario_id INTEGER NOT NULL,
                total REAL NOT NULL,
                criado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (usuario_id) REFERENCES usuarios (id)
            );
            """
        )
        conexao.execute(
            """
            CREATE TABLE IF NOT EXISTS itens_pedido (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pedido_id INTEGER NOT NULL,
                produto_id INTEGER NOT NULL,
                nome_produto TEXT NOT NULL,
                quantidade INTEGER NOT NULL,
                preco_unitario REAL NOT NULL,
                FOREIGN KEY (pedido_id) REFERENCES pedidos (id),
                FOREIGN KEY (produto_id) REFERENCES produtos (id)
            );
            """
        )
        total_produtos = conexao.execute(
            "SELECT COUNT(*) FROM produtos"
        ).fetchone()[0]
        if total_produtos == 0:
            conexao.executemany(
                """
                INSERT INTO produtos
                    (nome, categoria, descricao, preco, quantidade, status, imagem)
                VALUES (?, ?, ?, ?, ?, 'Disponível', ?)
                """,
                [
                    ("Blazer Atelier", "Alfaiataria", "Corte impecável e tecido premium.", 899.90, 8, "alfaiataria.jpg"),
                    ("Bolsa Signature", "Acessórios", "Design atemporal para acompanhar você.", 1249.90, 5, "acessorios.jpg"),
                    ("Vestido Lumière", "Feminino", "Elegância leve para ocasiões especiais.", 749.90, 6, "vestido.jpg"),
                    ("Tênis Urban Lux", "Calçados", "Conforto e sofisticação em cada passo.", 589.90, 10, "calcados.jpg"),
                ],
            )


def listar_produtos():
    with conectar() as conexao:
        return conexao.execute("SELECT * FROM produtos ORDER BY id DESC").fetchall()


def buscar_produto(id_produto):
    with conectar() as conexao:
        return conexao.execute(
            "SELECT * FROM produtos WHERE id = ?",
            (id_produto,),
        ).fetchone()


def inserir_produto(
    nome, categoria, descricao, preco, quantidade, status="Disponível", imagem="editorial.jpg"
):
    with conectar() as conexao:
        conexao.execute(
            """
            INSERT INTO produtos (nome, categoria, descricao, preco, quantidade, status, imagem)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (nome, categoria, descricao, preco, quantidade, status, imagem),
        )


def atualizar_produto(
    id_produto, nome, categoria, descricao, preco, quantidade, status, imagem
):
    with conectar() as conexao:
        conexao.execute(
            """
            UPDATE produtos
            SET nome = ?, categoria = ?, descricao = ?, preco = ?, quantidade = ?, status = ?, imagem = ?
            WHERE id = ?
            """,
            (nome, categoria, descricao, preco, quantidade, status, imagem, id_produto),
        )


def alternar_status_produto(id_produto):
    with conectar() as conexao:
        produto = conexao.execute(
            "SELECT status FROM produtos WHERE id = ?", (id_produto,)
        ).fetchone()
        if produto is not None:
            novo_status = "Disponível" if produto["status"] == "Indisponível" else "Indisponível"
            conexao.execute(
                "UPDATE produtos SET status = ? WHERE id = ?",
                (novo_status, id_produto),
            )


def excluir_produto(id_produto):
    with conectar() as conexao:
        conexao.execute("DELETE FROM produtos WHERE id = ?", (id_produto,))


def criar_usuario(nome, email, senha_hash):
    with conectar() as conexao:
        cursor = conexao.execute(
            "INSERT INTO usuarios (nome, email, senha_hash) VALUES (?, ?, ?)",
            (nome, email, senha_hash),
        )
        return cursor.lastrowid


def buscar_usuario_por_email(email):
    with conectar() as conexao:
        return conexao.execute(
            "SELECT * FROM usuarios WHERE email = ?", (email,)
        ).fetchone()


def buscar_usuario_por_id(id_usuario):
    with conectar() as conexao:
        return conexao.execute(
            "SELECT id, nome, email FROM usuarios WHERE id = ?", (id_usuario,)
        ).fetchone()


def listar_pedidos_usuario(id_usuario):
    with conectar() as conexao:
        return conexao.execute(
            """
            SELECT p.id, p.total, p.criado_em,
                   GROUP_CONCAT(ip.nome_produto || ' × ' || ip.quantidade, ', ') AS itens
            FROM pedidos p
            JOIN itens_pedido ip ON ip.pedido_id = p.id
            WHERE p.usuario_id = ?
            GROUP BY p.id
            ORDER BY p.id DESC
            """,
            (id_usuario,),
        ).fetchall()


def finalizar_pedido(id_usuario, itens):
    with conectar() as conexao:
        conexao.execute("BEGIN IMMEDIATE")
        produtos_pedido = []
        total = 0

        for id_produto, quantidade in itens.items():
            produto = conexao.execute(
                "SELECT * FROM produtos WHERE id = ?", (id_produto,)
            ).fetchone()
            if (
                produto is None
                or produto["status"] != "Disponível"
                or produto["quantidade"] < quantidade
            ):
                raise ValueError(
                    f"Estoque insuficiente para {produto['nome'] if produto else 'um produto'}."
                )
            total += produto["preco"] * quantidade
            produtos_pedido.append((produto, quantidade))

        cursor = conexao.execute(
            "INSERT INTO pedidos (usuario_id, total) VALUES (?, ?)",
            (id_usuario, total),
        )
        id_pedido = cursor.lastrowid
        for produto, quantidade in produtos_pedido:
            conexao.execute(
                """
                INSERT INTO itens_pedido
                    (pedido_id, produto_id, nome_produto, quantidade, preco_unitario)
                VALUES (?, ?, ?, ?, ?)
                """,
                (id_pedido, produto["id"], produto["nome"], quantidade, produto["preco"]),
            )
            conexao.execute(
                "UPDATE produtos SET quantidade = quantidade - ? WHERE id = ?",
                (quantidade, produto["id"]),
            )
        return id_pedido


# Compatibilidade com nomes antigos do projeto
listar_tarefas = listar_produtos
buscar_tarefa = buscar_produto
inserir_tarefa = inserir_produto
atualizar_tarefa = atualizar_produto
alternar_status = alternar_status_produto
excluir_tarefa = excluir_produto
