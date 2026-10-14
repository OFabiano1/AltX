# isso aq guarda tudo do bot: xp, placar, grana, colecao, mudae.
# sqlite em modo wal, cada operacao e uma transacao atomica.
# caminho absoluto pra nao depender de onde o app foi aberto.

import json
import logging
import os
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path

log = logging.getLogger("alt.data")

DB_PATH = Path(__file__).parent / "data" / "alt.db"
LEGACY_XP = Path(__file__).parent / "data" / "xp.json"

# so escrita pega lock. leitura vai sem: no modo wal leitores concorrentes
# nao bloqueiam (cada chamada usa a propria conexao). BEGIN IMMEDIATE nas
# escritas + timeout 30s cuidam da concorrencia entre elas.
_lock = threading.Lock()

# coluna de placar para cada resultado. Mapeamento explícito em vez de
# derivar a chave do primeiro caractere da string.
COLUNA_PTP = {"vitoria": "v", "derrota": "d", "empate": "e"}


def env_int(nome: str, padrao: int) -> int:
    """int de env que nunca quebra o boot: valor ruim vira padrao com aviso."""
    bruto = (os.getenv(nome) or "").strip()
    if not bruto:
        return padrao
    try:
        return int(bruto)
    except ValueError:
        log.warning("env %s invalida (%r), usando padrao %d", nome, bruto, padrao)
        return padrao

SCHEMA = """
CREATE TABLE IF NOT EXISTS xp (
    user_id INTEGER PRIMARY KEY,
    xp      INTEGER NOT NULL DEFAULT 0,
    nivel   INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS ptp (
    user_id INTEGER PRIMARY KEY,
    v       INTEGER NOT NULL DEFAULT 0,
    d       INTEGER NOT NULL DEFAULT 0,
    e       INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS economia (
    user_id   INTEGER PRIMARY KEY,
    diamantes INTEGER NOT NULL DEFAULT 0,
    ametista  INTEGER NOT NULL DEFAULT 0,
    aura      TEXT,
    last_daily TEXT
);

CREATE TABLE IF NOT EXISTS colecao (
    user_id    INTEGER NOT NULL,
    axolotl_id TEXT NOT NULL,
    qtd        INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (user_id, axolotl_id)
);

CREATE TABLE IF NOT EXISTS auras (
    user_id INTEGER NOT NULL,
    aura_id TEXT NOT NULL,
    PRIMARY KEY (user_id, aura_id)
);

CREATE TABLE IF NOT EXISTS mudae_reminder (
    user_id    INTEGER PRIMARY KEY,
    channel_id INTEGER NOT NULL,
    guild_id   INTEGER NOT NULL DEFAULT 0,
    expires_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS voz_fixa (
    guild_id   INTEGER PRIMARY KEY,
    channel_id INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS deadlock_links (
    discord_id INTEGER PRIMARY KEY,
    steam_id   INTEGER NOT NULL,
    updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS github_seen (
    repo       TEXT PRIMARY KEY,
    sha        TEXT NOT NULL,
    updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS github_seen_events (
    event_id   TEXT PRIMARY KEY,
    updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS github_destinos (
    repo       TEXT NOT NULL,
    channel_id INTEGER NOT NULL,
    PRIMARY KEY (repo, channel_id)
);

CREATE TABLE IF NOT EXISTS diaria_feita (
    user_id  INTEGER NOT NULL,
    dia      TEXT NOT NULL,
    quest_id TEXT NOT NULL,
    PRIMARY KEY (user_id, dia, quest_id)
);

CREATE TABLE IF NOT EXISTS streak (
    user_id    INTEGER PRIMARY KEY,
    dias       INTEGER NOT NULL DEFAULT 0,
    ultimo_dia TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS digest_msg (
    dia        TEXT PRIMARY KEY,
    channel_id INTEGER NOT NULL,
    message_id INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS contadores (
    user_id INTEGER NOT NULL,
    dia     TEXT NOT NULL,
    chave   TEXT NOT NULL,
    valor   INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (user_id, dia, chave)
);

CREATE TABLE IF NOT EXISTS doces (
    user_id INTEGER PRIMARY KEY,
    doces   INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS bet_stats (
    user_id  INTEGER PRIMARY KEY,
    apostas  INTEGER NOT NULL DEFAULT 0,
    vitorias INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS buffs (
    user_id   INTEGER NOT NULL,
    tipo      TEXT NOT NULL,
    expira_em REAL NOT NULL,
    PRIMARY KEY (user_id, tipo)
);

CREATE TABLE IF NOT EXISTS mines_jogos (
    user_id INTEGER PRIMARY KEY,
    moeda   TEXT NOT NULL,
    valor   INTEGER NOT NULL,
    minas   TEXT NOT NULL,
    abertos TEXT NOT NULL DEFAULT ''
);
"""


@contextmanager
def _conectar():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30)
    # por-conexao (nao persistem): espera na trava, cache e temp em ram.
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA cache_size=-64000")
    conn.execute("PRAGMA temp_store=MEMORY")
    conn.execute("PRAGMA mmap_size=134217728")
    try:
        conn.row_factory = sqlite3.Row
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ─── níveis ───
def xp_para_proximo(nivel: int) -> int:
    return nivel * 100


def buscar_xp(user_id: int) -> tuple[int, int]:
    """retorna (xp, nivel). Números neutros para usuário desconhecido."""
    with _conectar() as conn:
        row = conn.execute(
            "SELECT xp, nivel FROM xp WHERE user_id = ?", (user_id,)
        ).fetchone()
    return (row["xp"], row["nivel"]) if row else (0, 1)


def ganhar_xp(user_id: int, ganho: int) -> tuple[int, int, bool]:
    """soma XP e resolve a subida de nível.

    Leitura, cálculo e escrita na mesma transação — é isso que elimina a
    corrupção que o JSON sofria.

    Retorna (xp, nivel, subiu).
    """
    with _lock, _conectar() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT xp, nivel FROM xp WHERE user_id = ?", (user_id,)
        ).fetchone()
        xp, nivel = (row["xp"], row["nivel"]) if row else (0, 1)

        xp = max(0, xp + ganho)
        subiu = False
        while xp >= xp_para_proximo(nivel):
            xp -= xp_para_proximo(nivel)
            nivel += 1
            subiu = True

        conn.execute(
            "INSERT INTO xp (user_id, xp, nivel) VALUES (?, ?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET xp = excluded.xp, nivel = excluded.nivel",
            (user_id, xp, nivel),
        )
        return xp, nivel, subiu


def definir_xp(user_id: int, xp: int) -> tuple[int, int]:
    """define o XP total acumulado e deriva o nível dele.

    Retorna (xp, nivel).
    """
    with _lock, _conectar() as conn:
        conn.execute("BEGIN IMMEDIATE")
        xp = max(0, xp)
        nivel = 1
        while xp >= xp_para_proximo(nivel):
            xp -= xp_para_proximo(nivel)
            nivel += 1

        conn.execute(
            "INSERT INTO xp (user_id, xp, nivel) VALUES (?, ?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET xp = excluded.xp, nivel = excluded.nivel",
            (user_id, xp, nivel),
        )
        return xp, nivel


def top_xp(limite: int = 10) -> list[tuple[int, int, int]]:
    """top N por nível, desempate por XP. Retorna [(user_id, nivel, xp)]."""
    with _conectar() as conn:
        rows = conn.execute(
            "SELECT user_id, nivel, xp FROM xp "
            "ORDER BY nivel DESC, xp DESC LIMIT ?",
            (limite,),
        ).fetchall()
    return [(r["user_id"], r["nivel"], r["xp"]) for r in rows]


# ─── pedra, tesoura e papel ───
def buscar_ptp(user_id: int) -> tuple[int, int, int]:
    """retorna (vitorias, derrotas, empates)."""
    with _conectar() as conn:
        row = conn.execute(
            "SELECT v, d, e FROM ptp WHERE user_id = ?", (user_id,)
        ).fetchone()
    return (row["v"], row["d"], row["e"]) if row else (0, 0, 0)


def registrar_ptp(user_id: int, resultado: str) -> tuple[int, int, int]:
    """registra uma jogada e devolve o placar atualizado (v, d, e)."""
    # `coluna` só pode ser uma das três chaves de COLUNA_PTP — o dict é a
    # validação, o valor do usuário nunca entra no SQL.
    coluna = COLUNA_PTP[resultado]
    with _lock, _conectar() as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            f"INSERT INTO ptp (user_id, {coluna}) VALUES (?, 1) "
            f"ON CONFLICT(user_id) DO UPDATE SET {coluna} = {coluna} + 1",
            (user_id,),
        )
        row = conn.execute(
            "SELECT v, d, e FROM ptp WHERE user_id = ?", (user_id,)
        ).fetchone()
        return row["v"], row["d"], row["e"]


def top_ptp(limite: int = 5) -> list[tuple[int, int, int, int]]:
    """top N por vitórias. Retorna [(user_id, v, d, e)]."""
    with _conectar() as conn:
        rows = conn.execute(
            "SELECT user_id, v, d, e FROM ptp "
            "WHERE (v + d + e) > 0 ORDER BY v DESC, e DESC LIMIT ?",
            (limite,),
        ).fetchall()
    return [(r["user_id"], r["v"], r["d"], r["e"]) for r in rows]


# ─── economia (diamantes + ametista + aura) ───
def buscar_saldo(user_id: int) -> tuple[int, int, str | None]:
    """retorna (diamantes, ametista, aura_equipadada)."""
    with _conectar() as conn:
        row = conn.execute(
            "SELECT diamantes, ametista, aura FROM economia WHERE user_id = ?",
            (user_id,),
        ).fetchone()
    if row:
        return row["diamantes"], row["ametista"], row["aura"]
    return 0, 0, None


def buscar_daily(user_id: int) -> str | None:
    """ultimo dia (YYYY-MM-DD UTC) que resgatou o daily, ou None."""
    with _conectar() as conn:
        row = conn.execute(
            "SELECT last_daily FROM economia WHERE user_id = ?", (user_id,)
        ).fetchone()
    return row["last_daily"] if row else None


def adicionar_diamantes(user_id: int, qtd: int) -> int:
    """soma (ou subtrai se negativo) diamantes. Nunca deixa negativo. Retorna total."""
    with _lock, _conectar() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT diamantes FROM economia WHERE user_id = ?", (user_id,)
        ).fetchone()
        total = (row["diamantes"] if row else 0) + qtd
        total = max(0, total)
        conn.execute(
            "INSERT INTO economia (user_id, diamantes) VALUES (?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET diamantes = ?",
            (user_id, total, total),
        )
        return total


def adicionar_ametista(user_id: int, qtd: int) -> int:
    """soma (ou subtrai se negativo) ametista. Nunca deixa negativo. Retorna total."""
    with _lock, _conectar() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT ametista FROM economia WHERE user_id = ?", (user_id,)
        ).fetchone()
        total = (row["ametista"] if row else 0) + qtd
        total = max(0, total)
        conn.execute(
            "INSERT INTO economia (user_id, ametista) VALUES (?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET ametista = ?",
            (user_id, total, total),
        )
        return total


def transferir_diamantes(origem: int, destino: int, qtd: int) -> tuple[bool, int, int]:
    """transfere diamantes entre usuários. Retorna (ok, saldo_origem, saldo_destino)."""
    if qtd <= 0 or origem == destino:
        s_o, _, _ = buscar_saldo(origem)
        s_d, _, _ = buscar_saldo(destino)
        return False, s_o, s_d
    with _lock, _conectar() as conn:
        conn.execute("BEGIN IMMEDIATE")
        r1 = conn.execute(
            "SELECT diamantes FROM economia WHERE user_id = ?", (origem,)
        ).fetchone()
        s_origem = r1["diamantes"] if r1 else 0
        if s_origem < qtd:
            return False, s_origem, (
                conn.execute(
                    "SELECT diamantes FROM economia WHERE user_id = ?", (destino,)
                ).fetchone() or {"diamantes": 0}
            )["diamantes"]
        r2 = conn.execute(
            "SELECT diamantes FROM economia WHERE user_id = ?", (destino,)
        ).fetchone()
        s_dest = r2["diamantes"] if r2 else 0
        conn.execute(
            "INSERT INTO economia (user_id, diamantes) VALUES (?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET diamantes = ?",
            (origem, s_origem - qtd, s_origem - qtd),
        )
        conn.execute(
            "INSERT INTO economia (user_id, diamantes) VALUES (?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET diamantes = ?",
            (destino, s_dest + qtd, s_dest + qtd),
        )
        return True, s_origem - qtd, s_dest + qtd


def tentar_daily(user_id: int, dima: int, amet: int, hoje: str) -> tuple[bool, int, int]:
    """tenta resgatar o daily. Retorna (ok, diamantes, ametista).

    `hoje` é YYYY-MM-DD em UTC. Se last_daily == hoje, nega.
    """
    with _lock, _conectar() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT diamantes, ametista, last_daily FROM economia WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        if row and row["last_daily"] == hoje:
            return False, row["diamantes"], row["ametista"]
        d_total = (row["diamantes"] if row else 0) + dima
        a_total = (row["ametista"] if row else 0) + amet
        conn.execute(
            "INSERT INTO economia (user_id, diamantes, ametista, last_daily) "
            "VALUES (?, ?, ?, ?) ON CONFLICT(user_id) DO UPDATE SET "
            "diamantes = excluded.diamantes, ametista = excluded.ametista, "
            "last_daily = excluded.last_daily",
            (user_id, d_total, a_total, hoje),
        )
        return True, d_total, a_total


def top_diamantes(limite: int = 10) -> list[tuple[int, int]]:
    """top N por diamantes. Retorna [(user_id, diamantes)]."""
    with _conectar() as conn:
        rows = conn.execute(
            "SELECT user_id, diamantes FROM economia "
            "WHERE diamantes > 0 ORDER BY diamantes DESC LIMIT ?",
            (limite,),
        ).fetchall()
    return [(r["user_id"], r["diamantes"]) for r in rows]


# ─── auras ───
def tem_aura(user_id: int, aura_id: str) -> bool:
    with _conectar() as conn:
        row = conn.execute(
            "SELECT 1 FROM auras WHERE user_id = ? AND aura_id = ?",
            (user_id, aura_id),
        ).fetchone()
    return row is not None


def dar_aura(user_id: int, aura_id: str) -> None:
    with _lock, _conectar() as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            "INSERT OR IGNORE INTO auras (user_id, aura_id) VALUES (?, ?)",
            (user_id, aura_id),
        )


def auras_usuario(user_id: int) -> list[str]:
    with _conectar() as conn:
        rows = conn.execute(
            "SELECT aura_id FROM auras WHERE user_id = ?", (user_id,)
        ).fetchall()
    return [r["aura_id"] for r in rows]


def equipar_aura(user_id: int, aura_id: str | None) -> None:
    with _lock, _conectar() as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            "INSERT INTO economia (user_id, aura) VALUES (?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET aura = excluded.aura",
            (user_id, aura_id),
        )


# ─── coleção de axolotls ───
def adicionar_axolotl(user_id: int, axolotl_id: str) -> int:
    """incrementa a coleção. Retorna a qtd atual daquele axolotl."""
    with _lock, _conectar() as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            "INSERT INTO colecao (user_id, axolotl_id, qtd) VALUES (?, ?, 1) "
            "ON CONFLICT(user_id, axolotl_id) DO UPDATE SET qtd = qtd + 1",
            (user_id, axolotl_id),
        )
        row = conn.execute(
            "SELECT qtd FROM colecao WHERE user_id = ? AND axolotl_id = ?",
            (user_id, axolotl_id),
        ).fetchone()
        return row["qtd"]


def buscar_colecao(user_id: int) -> list[tuple[str, int]]:
    """retorna [(axolotl_id, qtd)]."""
    with _conectar() as conn:
        rows = conn.execute(
            "SELECT axolotl_id, qtd FROM colecao WHERE user_id = ? ORDER BY qtd DESC",
            (user_id,),
        ).fetchall()
    return [(r["axolotl_id"], r["qtd"]) for r in rows]


# ─── mudae reminder ───
def salvar_mudae(user_id: int, channel_id: int, guild_id: int, expires_at: float) -> None:
    """agenda/substitui o reminder. Um ativo por usuário."""
    with _lock, _conectar() as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            "INSERT INTO mudae_reminder (user_id, channel_id, guild_id, expires_at) "
            "VALUES (?, ?, ?, ?) ON CONFLICT(user_id) DO UPDATE SET "
            "channel_id = excluded.channel_id, guild_id = excluded.guild_id, "
            "expires_at = excluded.expires_at",
            (user_id, channel_id, guild_id, expires_at),
        )


def remover_mudae(user_id: int) -> None:
    with _lock, _conectar() as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("DELETE FROM mudae_reminder WHERE user_id = ?", (user_id,))


def listar_mudae() -> list[tuple[int, int, int, float]]:
    """retorna [(user_id, channel_id, guild_id, expires_at)]."""
    with _conectar() as conn:
        rows = conn.execute(
            "SELECT user_id, channel_id, guild_id, expires_at FROM mudae_reminder"
        ).fetchall()
    return [(r["user_id"], r["channel_id"], r["guild_id"], r["expires_at"]) for r in rows]


# ─── voz fixa ───
def fixar_voz(guild_id: int, channel_id: int) -> None:
    """marca a call pra ficar. sobrevivem restart e queda."""
    with _lock, _conectar() as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            "INSERT INTO voz_fixa (guild_id, channel_id) VALUES (?, ?) "
            "ON CONFLICT(guild_id) DO UPDATE SET channel_id = excluded.channel_id",
            (guild_id, channel_id),
        )


def soltar_voz(guild_id: int) -> None:
    """desmarca a call. so o >sair chama isso."""
    with _lock, _conectar() as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("DELETE FROM voz_fixa WHERE guild_id = ?", (guild_id,))


def voz_fixa(guild_id: int) -> int | None:
    """devolve a call fixada ou None."""
    with _conectar() as conn:
        row = conn.execute(
            "SELECT channel_id FROM voz_fixa WHERE guild_id = ?", (guild_id,)
        ).fetchone()
    return row["channel_id"] if row else None


# ─── vínculo deadlock (discord -> steam) ───
def vincular_deadlock(discord_id: int, steam_id: int) -> None:
    """salva/troca o vínculo deadlock. um por usuário."""
    import time

    with _lock, _conectar() as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            "INSERT INTO deadlock_links (discord_id, steam_id, updated_at) "
            "VALUES (?, ?, ?) ON CONFLICT(discord_id) DO UPDATE SET "
            "steam_id = excluded.steam_id, updated_at = excluded.updated_at",
            (discord_id, steam_id, time.time()),
        )


def desvincular_deadlock(discord_id: int) -> bool:
    """remove o vínculo. retorna True se existia."""
    with _lock, _conectar() as conn:
        conn.execute("BEGIN IMMEDIATE")
        cur = conn.execute(
            "DELETE FROM deadlock_links WHERE discord_id = ?", (discord_id,)
        )
        return cur.rowcount > 0


def buscar_deadlock(discord_id: int) -> int | None:
    """devolve o steam_id vinculado ou None."""
    with _conectar() as conn:
        row = conn.execute(
            "SELECT steam_id FROM deadlock_links WHERE discord_id = ?",
            (discord_id,),
        ).fetchone()
    return int(row["steam_id"]) if row else None


# ─── github monitorado ───
def buscar_github(repo: str) -> str | None:
    """ultimo sha postado do repo, ou None (primeira vez)."""
    with _conectar() as conn:
        row = conn.execute(
            "SELECT sha FROM github_seen WHERE repo = ?", (repo,)
        ).fetchone()
    return row["sha"] if row else None


def salvar_github(repo: str, sha: str) -> None:
    """marca o sha como ja postado."""
    import time

    with _lock, _conectar() as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            "INSERT INTO github_seen (repo, sha, updated_at) VALUES (?, ?, ?) "
            "ON CONFLICT(repo) DO UPDATE SET sha = excluded.sha, "
            "updated_at = excluded.updated_at",
            (repo, sha, time.time()),
        )


def viu_evento(event_id: str) -> bool:
    """True se o evento do github ja foi postado."""
    with _conectar() as conn:
        row = conn.execute(
            "SELECT 1 FROM github_seen_events WHERE event_id = ?", (event_id,)
        ).fetchone()
    return row is not None


def salvar_evento(event_id: str) -> None:
    """marca o evento como ja postado."""
    import time

    with _lock, _conectar() as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            "INSERT OR IGNORE INTO github_seen_events (event_id, updated_at) "
            "VALUES (?, ?)",
            (event_id, time.time()),
        )


# ─── diarias e streak ───
def marcar_feita(user_id: int, dia: str, quest_id: str) -> bool:
    """marca quest do dia. True se foi a primeira vez (vale xp)."""
    with _lock, _conectar() as conn:
        conn.execute("BEGIN IMMEDIATE")
        cur = conn.execute(
            "INSERT OR IGNORE INTO diaria_feita (user_id, dia, quest_id) "
            "VALUES (?, ?, ?)",
            (user_id, dia, quest_id),
        )
        return cur.rowcount > 0


def feitas_no_dia(user_id: int, dia: str) -> list[str]:
    """quest_ids feitas no dia."""
    with _conectar() as conn:
        rows = conn.execute(
            "SELECT quest_id FROM diaria_feita WHERE user_id = ? AND dia = ?",
            (user_id, dia),
        ).fetchall()
    return [r["quest_id"] for r in rows]


def quem_jogou(dia: str) -> list[int]:
    """quem fez ao menos 1 quest no dia."""
    with _conectar() as conn:
        rows = conn.execute(
            "SELECT DISTINCT user_id FROM diaria_feita WHERE dia = ?", (dia,)
        ).fetchall()
    return [r["user_id"] for r in rows]


def buscar_streak(user_id: int) -> tuple[int, str]:
    """retorna (dias, ultimo_dia)."""
    with _conectar() as conn:
        row = conn.execute(
            "SELECT dias, ultimo_dia FROM streak WHERE user_id = ?", (user_id,)
        ).fetchone()
    return (row["dias"], row["ultimo_dia"]) if row else (0, "")


def salvar_streak(user_id: int, dias: int, ultimo_dia: str) -> None:
    with _lock, _conectar() as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            "INSERT INTO streak (user_id, dias, ultimo_dia) VALUES (?, ?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET dias = excluded.dias, "
            "ultimo_dia = excluded.ultimo_dia",
            (user_id, dias, ultimo_dia),
        )


def streak_ativos() -> list[tuple[int, int, str]]:
    """quem tem streak > 0: [(user_id, dias, ultimo_dia)]."""
    with _conectar() as conn:
        rows = conn.execute(
            "SELECT user_id, dias, ultimo_dia FROM streak WHERE dias > 0"
        ).fetchall()
    return [(r["user_id"], r["dias"], r["ultimo_dia"]) for r in rows]


def buscar_discord_por_steam(steam_id: int) -> int | None:
    """discord dono da steam vinculada, ou None."""
    with _conectar() as conn:
        row = conn.execute(
            "SELECT discord_id FROM deadlock_links WHERE steam_id = ?", (steam_id,)
        ).fetchone()
    return int(row["discord_id"]) if row else None


def listar_deadlocks() -> list[tuple[int, int]]:
    """todos os vinculos [(discord_id, steam_id)]."""
    with _conectar() as conn:
        rows = conn.execute("SELECT discord_id, steam_id FROM deadlock_links").fetchall()
    return [(r["discord_id"], r["steam_id"]) for r in rows]


def salvar_digest(dia: str, channel_id: int, message_id: int) -> None:
    with _lock, _conectar() as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            "INSERT INTO digest_msg (dia, channel_id, message_id) VALUES (?, ?, ?) "
            "ON CONFLICT(dia) DO UPDATE SET channel_id = excluded.channel_id, "
            "message_id = excluded.message_id",
            (dia, channel_id, message_id),
        )


def buscar_digest(dia: str) -> tuple[int, int] | None:
    """(channel_id, message_id) do digest do dia, ou None."""
    with _conectar() as conn:
        row = conn.execute(
            "SELECT channel_id, message_id FROM digest_msg WHERE dia = ?", (dia,)
        ).fetchone()
    return (row["channel_id"], row["message_id"]) if row else None


# ─── contadores (ex: msgs do dia pra quest) ───
def somar_contador(user_id: int, dia: str, chave: str, ganho: int = 1) -> int:
    """soma e retorna o total."""
    with _lock, _conectar() as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            "INSERT INTO contadores (user_id, dia, chave, valor) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(user_id, dia, chave) DO NOTHING",
            (user_id, dia, chave, 0),
        )
        conn.execute(
            "UPDATE contadores SET valor = valor + ? "
            "WHERE user_id = ? AND dia = ? AND chave = ?",
            (ganho, user_id, dia, chave),
        )
        row = conn.execute(
            "SELECT valor FROM contadores WHERE user_id = ? AND dia = ? AND chave = ?",
            (user_id, dia, chave),
        ).fetchone()
        return row["valor"]


# ─── destinos do github (repo -> chats) ───
def vincular_repo(repo: str, channel_id: int) -> None:
    """liga um repo ao chat. idempotente."""
    with _lock, _conectar() as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            "INSERT OR IGNORE INTO github_destinos (repo, channel_id) "
            "VALUES (?, ?)",
            (repo, channel_id),
        )


def desvincular_repo(repo: str, channel_id: int) -> bool:
    """tira o repo do chat. True se existia."""
    with _lock, _conectar() as conn:
        conn.execute("BEGIN IMMEDIATE")
        cur = conn.execute(
            "DELETE FROM github_destinos WHERE repo = ? AND channel_id = ?",
            (repo, channel_id),
        )
        return cur.rowcount > 0


def destinos_repo(repo: str) -> list[int]:
    """chats vinculados ao repo."""
    with _conectar() as conn:
        rows = conn.execute(
            "SELECT channel_id FROM github_destinos WHERE repo = ?", (repo,)
        ).fetchall()
    return [r["channel_id"] for r in rows]


def listar_destinos() -> list[tuple[str, int]]:
    """todos os vinculos [(repo, channel_id)]."""
    with _conectar() as conn:
        rows = conn.execute(
            "SELECT repo, channel_id FROM github_destinos ORDER BY repo"
        ).fetchall()
    return [(r["repo"], r["channel_id"]) for r in rows]


# ─── doces de halloween ───
def buscar_doces(user_id: int) -> int:
    """total de doces do usuario."""
    with _conectar() as conn:
        row = conn.execute(
            "SELECT doces FROM doces WHERE user_id = ?", (user_id,)
        ).fetchone()
    return row["doces"] if row else 0


def ganhar_doces(user_id: int, qtd: int) -> int:
    """soma doces. retorna o total."""
    with _lock, _conectar() as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            "INSERT INTO doces (user_id, doces) VALUES (?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET doces = doces + ?",
            (user_id, qtd, qtd),
        )
        row = conn.execute(
            "SELECT doces FROM doces WHERE user_id = ?", (user_id,)
        ).fetchone()
        return row["doces"]


def gastar_doces(user_id: int, qtd: int) -> tuple[bool, int]:
    """gasta doces se tiver saldo. retorna (ok, total_atual)."""
    if qtd <= 0:
        return False, buscar_doces(user_id)
    with _lock, _conectar() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT doces FROM doces WHERE user_id = ?", (user_id,)
        ).fetchone()
        total = row["doces"] if row else 0
        if total < qtd:
            return False, total
        total -= qtd
        conn.execute(
            "INSERT INTO doces (user_id, doces) VALUES (?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET doces = ?",
            (user_id, total, total),
        )
        return True, total


def top_doces(limite: int = 5) -> list[tuple[int, int]]:
    """top N por doces. retorna [(user_id, doces)]."""
    with _conectar() as conn:
        rows = conn.execute(
            "SELECT user_id, doces FROM doces "
            "WHERE doces > 0 ORDER BY doces DESC LIMIT ?",
            (limite,),
        ).fetchall()
    return [(r["user_id"], r["doces"]) for r in rows]


# ─── apostas (axolotl bet: so contagem, sem valor — dima e amet nao se somam) ───
def registrar_aposta(user_id: int, venceu: bool) -> None:
    """soma 1 aposta (e 1 vitoria se venceu)."""
    with _lock, _conectar() as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            "INSERT INTO bet_stats (user_id, apostas, vitorias) VALUES (?, 1, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET apostas = apostas + 1, "
            "vitorias = vitorias + ?",
            (user_id, 1 if venceu else 0, 1 if venceu else 0),
        )


def buscar_bet(user_id: int) -> tuple[int, int]:
    """retorna (apostas, vitorias)."""
    with _conectar() as conn:
        row = conn.execute(
            "SELECT apostas, vitorias FROM bet_stats WHERE user_id = ?", (user_id,)
        ).fetchone()
    return (row["apostas"], row["vitorias"]) if row else (0, 0)


def posicao_xp(user_id: int) -> int | None:
    """posicao no ranking (1 = top). None se sem xp."""
    with _conectar() as conn:
        row = conn.execute(
            "SELECT nivel, xp FROM xp WHERE user_id = ?", (user_id,)
        ).fetchone()
        if row is None:
            return None
        n = conn.execute(
            "SELECT COUNT(*) FROM xp WHERE nivel > ? OR (nivel = ? AND xp > ?)",
            (row["nivel"], row["nivel"], row["xp"]),
        ).fetchone()[0]
        return n + 1


def cortar_diamantes() -> tuple[int, int, int]:
    """divide os diamantes de todo mundo por 2 (floor). retorna (afetados, antes, depois)."""
    with _lock, _conectar() as conn:
        conn.execute("BEGIN IMMEDIATE")
        antes = (
            conn.execute("SELECT COALESCE(SUM(diamantes), 0) FROM economia").fetchone()[0]
        )
        cur = conn.execute(
            "UPDATE economia SET diamantes = CAST(diamantes / 2 AS INTEGER) "
            "WHERE diamantes > 0"
        )
        depois = (
            conn.execute("SELECT COALESCE(SUM(diamantes), 0) FROM economia").fetchone()[0]
        )
        return cur.rowcount, antes, depois


# ─── buffs 2x (xp2, dima2: multiplica o ganho por msg) ───
def dar_buff(user_id: int, tipo: str, segundos: int) -> None:
    """liga/estende o buff. expira = max(agora, atual) + duracao."""
    import time

    with _lock, _conectar() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT expira_em FROM buffs WHERE user_id = ? AND tipo = ?",
            (user_id, tipo),
        ).fetchone()
        base = max(time.time(), row["expira_em"]) if row else time.time()
        conn.execute(
            "INSERT INTO buffs (user_id, tipo, expira_em) VALUES (?, ?, ?) "
            "ON CONFLICT(user_id, tipo) DO UPDATE SET expira_em = excluded.expira_em",
            (user_id, tipo, base + segundos),
        )


def buffs_ativos(user_id: int) -> dict[str, int]:
    """{tipo: segundos restantes}. limpa os vencidos de passagem."""
    import time

    agora = time.time()
    with _lock, _conectar() as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("DELETE FROM buffs WHERE user_id = ? AND expira_em <= ?", (user_id, agora))
        rows = conn.execute(
            "SELECT tipo, expira_em FROM buffs WHERE user_id = ?", (user_id,)
        ).fetchall()
    return {r["tipo"]: int(r["expira_em"] - agora) for r in rows}


def buff_ativo(user_id: int, tipo: str) -> int:
    """segundos restantes do buff, 0 se acabou."""
    return buffs_ativos(user_id).get(tipo, 0)


# ─── mines (jogo persistido: restart devolve a aposta) ───
def _csv(vals: set[int]) -> str:
    return ",".join(str(v) for v in sorted(vals))


def _de_csv(texto: str) -> set[int]:
    return {int(x) for x in (texto or "").split(",") if x.strip().isdigit()}


def _linha_mines(row) -> dict:
    return {
        "user_id": row["user_id"],
        "moeda": row["moeda"],
        "valor": row["valor"],
        "minas": _de_csv(row["minas"]),
        "abertos": _de_csv(row["abertos"]),
    }


def salvar_mines(user_id: int, moeda: str, valor: int, minas: set[int]) -> None:
    """guarda jogo novo (zera os abertos)."""
    with _lock, _conectar() as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            "INSERT INTO mines_jogos (user_id, moeda, valor, minas, abertos) "
            "VALUES (?, ?, ?, ?, '') ON CONFLICT(user_id) DO UPDATE SET "
            "moeda = excluded.moeda, valor = excluded.valor, "
            "minas = excluded.minas, abertos = ''",
            (user_id, moeda, valor, _csv(minas)),
        )


def buscar_mines(user_id: int) -> dict | None:
    with _conectar() as conn:
        row = conn.execute(
            "SELECT * FROM mines_jogos WHERE user_id = ?", (user_id,)
        ).fetchone()
    return _linha_mines(row) if row is not None else None


def abrir_mines(user_id: int, idx: int) -> tuple[dict | None, bool]:
    """marca a pedra aberta. retorna (jogo, nova?) — (None, False) se sem jogo."""
    with _lock, _conectar() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT * FROM mines_jogos WHERE user_id = ?", (user_id,)
        ).fetchone()
        if row is None:
            return None, False
        abertos = _de_csv(row["abertos"])
        nova = idx not in abertos
        abertos.add(idx)
        conn.execute(
            "UPDATE mines_jogos SET abertos = ? WHERE user_id = ?",
            (_csv(abertos), user_id),
        )
        jogo = _linha_mines(row)
        jogo["abertos"] = abertos
        return jogo, nova


def remover_mines(user_id: int) -> dict | None:
    """tira o jogo e devolve ele (pra reembolsar). None se nao tinha."""
    with _lock, _conectar() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT * FROM mines_jogos WHERE user_id = ?", (user_id,)
        ).fetchone()
        if row is None:
            return None
        conn.execute("DELETE FROM mines_jogos WHERE user_id = ?", (user_id,))
        return _linha_mines(row)


def listar_mines() -> list[dict]:
    """todos os jogos abertos (reembolso pos-restart)."""
    with _conectar() as conn:
        rows = conn.execute("SELECT * FROM mines_jogos").fetchall()
    return [_linha_mines(r) for r in rows]


# ─── reset total (admin: limpa o player sem deixar resto) ───
def reset_usuario(user_id: int) -> int:
    """apaga tudo do usuario em todas as tabelas. retorna linhas apagadas."""
    alvos = [
        ("xp", "user_id"),
        ("ptp", "user_id"),
        ("economia", "user_id"),
        ("colecao", "user_id"),
        ("auras", "user_id"),
        ("mudae_reminder", "user_id"),
        ("deadlock_links", "discord_id"),
        ("bet_stats", "user_id"),
        ("buffs", "user_id"),
        ("mines_jogos", "user_id"),
        ("doces", "user_id"),
        ("diaria_feita", "user_id"),
        ("streak", "user_id"),
        ("contadores", "user_id"),
        ("quest_progress", "user_id"),
        ("voice_time", "user_id"),
    ]
    total = 0
    with _lock, _conectar() as conn:
        conn.execute("BEGIN IMMEDIATE")
        for tabela, coluna in alvos:
            try:
                cur = conn.execute(
                    f"DELETE FROM {tabela} WHERE {coluna} = ?", (user_id,)
                )
                total += cur.rowcount
            except Exception:
                continue
    return total


# ─── debito atomico (apostas, loja, caixas: checa e tira numa transacao) ───
def debitar_moeda(user_id: int, moeda: str, valor: int) -> tuple[bool, int]:
    """tira valor se tiver saldo. retorna (ok, saldo_atual). Sem saldo = sem mudanca."""
    if valor <= 0 or moeda not in ("dima", "amet"):
        return False, 0
    coluna = "diamantes" if moeda == "dima" else "ametista"
    with _lock, _conectar() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            f"SELECT {coluna} FROM economia WHERE user_id = ?", (user_id,)
        ).fetchone()
        saldo = row[coluna] if row else 0
        if saldo < valor:
            return False, saldo
        novo = saldo - valor
        conn.execute(
            f"INSERT INTO economia (user_id, {coluna}) VALUES (?, ?) "
            f"ON CONFLICT(user_id) DO UPDATE SET {coluna} = ?",
            (user_id, novo, novo),
        )
        return True, novo


# ─── snapshot do player (tudo numa conexao so: abre rapido) ───
def snapshot(user_id: int, hoje: str) -> dict:
    """tudo que o >player precisa, numa leitura so.

    retorna {xp, nivel, dima, amet, aura, colecao, apostas, vitorias,
    doces, daily, feitas, streak, ptp, steam}. colecao: [(axolotl_id, qtd)].
    """
    with _conectar() as conn:
        r = conn.execute(
            "SELECT xp, nivel FROM xp WHERE user_id = ?", (user_id,)
        ).fetchone()
        xp, nivel = (r["xp"], r["nivel"]) if r else (0, 1)

        r = conn.execute(
            "SELECT diamantes, ametista, aura, last_daily FROM economia WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        dima, amet, aura, daily = (
            (r["diamantes"], r["ametista"], r["aura"], r["last_daily"])
            if r
            else (0, 0, None, None)
        )

        colecao = [
            (x["axolotl_id"], x["qtd"])
            for x in conn.execute(
                "SELECT axolotl_id, qtd FROM colecao WHERE user_id = ? ORDER BY qtd DESC",
                (user_id,),
            ).fetchall()
        ]

        r = conn.execute(
            "SELECT apostas, vitorias FROM bet_stats WHERE user_id = ?", (user_id,)
        ).fetchone()
        apostas, vitorias = (r["apostas"], r["vitorias"]) if r else (0, 0)

        r = conn.execute(
            "SELECT doces FROM doces WHERE user_id = ?", (user_id,)
        ).fetchone()
        doces = r["doces"] if r else 0

        feitas = [
            x["quest_id"]
            for x in conn.execute(
                "SELECT quest_id FROM diaria_feita WHERE user_id = ? AND dia = ?",
                (user_id, hoje),
            ).fetchall()
        ]

        r = conn.execute(
            "SELECT dias FROM streak WHERE user_id = ?", (user_id,)
        ).fetchone()
        streak = r["dias"] if r else 0

        r = conn.execute(
            "SELECT v, d, e FROM ptp WHERE user_id = ?", (user_id,)
        ).fetchone()
        ptp = (r["v"], r["d"], r["e"]) if r else (0, 0, 0)

        r = conn.execute(
            "SELECT steam_id FROM deadlock_links WHERE discord_id = ?", (user_id,)
        ).fetchone()
        steam = int(r["steam_id"]) if r else None

        import time as _time

        agora_ts = _time.time()
        buffs = {
            x["tipo"]: int(x["expira_em"] - agora_ts)
            for x in conn.execute(
                "SELECT tipo, expira_em FROM buffs WHERE user_id = ? AND expira_em > ?",
                (user_id, agora_ts),
            ).fetchall()
        }

        tem_xp = (
            conn.execute(
                "SELECT 1 FROM xp WHERE user_id = ?", (user_id,)
            ).fetchone()
            is not None
        )
        pos = (
            conn.execute(
                "SELECT COUNT(*) FROM xp WHERE nivel > ? OR (nivel = ? AND xp > ?)",
                (nivel, nivel, xp),
            ).fetchone()[0]
            + 1
            if tem_xp
            else None
        )
    return {
        "xp": xp,
        "nivel": nivel,
        "dima": dima,
        "amet": amet,
        "aura": aura,
        "colecao": colecao,
        "apostas": apostas,
        "vitorias": vitorias,
        "doces": doces,
        "daily": daily,
        "feitas": feitas,
        "streak": streak,
        "ptp": ptp,
        "steam": steam,
        "buffs": buffs,
        "pos": pos,
    }


# ─── backup ───

BACKUP_DIR = DB_PATH.parent / "backups"


def backup(keep: int = 7):
    """copia consistente do banco (api de backup do sqlite, pega o wal junto).

    guarda em data/backups/ com retencao dos N mais novos.
    retorna o arquivo ou None se nem tem banco ainda.
    """
    import datetime as _dt

    if not DB_PATH.exists():
        return None
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    destino = BACKUP_DIR / ("alt-%s.db" % _dt.datetime.now().strftime("%Y%m%d-%H%M"))
    with _lock:
        origem = sqlite3.connect(DB_PATH, timeout=30)
        try:
            alvo = sqlite3.connect(destino)
            try:
                origem.backup(alvo)
            finally:
                alvo.close()
        finally:
            origem.close()
    arquivos = sorted(BACKUP_DIR.glob("alt-*.db"), key=lambda p: p.name)
    for velho in arquivos[:-keep] if len(arquivos) > keep else []:
        velho.unlink(missing_ok=True)
    return destino


def verificar_backup(caminho) -> bool:
    """True se integrity_check passa e as tabelas abrem (teste de restore)."""
    from urllib.request import pathname2url

    try:
        # pathname2url: `#` no caminho (ex `#Projetos`) virava fragmento no modo uri.
        conn = sqlite3.connect(
            f"file:{pathname2url(str(caminho))}?mode=ro", uri=True, timeout=10
        )
        try:
            ok = conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            conn.execute("SELECT COUNT(*) FROM xp").fetchone()
            conn.execute("SELECT COUNT(*) FROM economia").fetchone()
            return ok
        finally:
            conn.close()
    except Exception:
        return False


# ─── migração ───
def migrar_xp_legado() -> int:
    """importa data/xp.json uma única vez, se ele existir.

    Sem isso, todo o nível acumulado antes do SQLite seria perdido no
    primeiro deploy. Só roda se a tabela xp estiver vazia.
    """
    if not LEGACY_XP.exists():
        return 0

    with _lock, _conectar() as conn:
        tem_tabela = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'xp'"
        ).fetchone()
        if not tem_tabela:
            return 0

        total = conn.execute("SELECT COUNT(*) FROM xp").fetchone()[0]
        if total:
            return 0

        try:
            with open(LEGACY_XP, "r", encoding="utf-8") as f:
                dados = json.load(f)
        except (json.JSONDecodeError, OSError):
            return 0

        inseridos = 0
        for uid, dados_user in dados.items():
            try:
                user_id = int(uid)
                xp = int(dados_user["xp"])
                nivel = int(dados_user["nivel"])
            except (KeyError, TypeError, ValueError):
                continue
            conn.execute(
                "INSERT OR IGNORE INTO xp (user_id, xp, nivel) VALUES (?, ?, ?)",
                (user_id, max(0, xp), max(1, nivel)),
            )
            inseridos += 1

    return inseridos


def init() -> None:
    """cria o schema e migra dados legados. idempotente."""
    with _lock, _conectar() as conn:
        conn.executescript(SCHEMA)
        # wal e sync persistem no arquivo, configura uma vez so aqui
        # em vez de repetir em toda conexao (toda msg de xp).
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        # conquistas desativadas: limpa a tabela onde existir (vale no deploy).
        conn.execute("DROP TABLE IF EXISTS conquistas")
    migrar_xp_legado()
