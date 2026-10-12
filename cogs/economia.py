import asyncio
import os
import random
from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands

import visual
import data

# ─── ganhos ───
DAILY_DIAMANTES = 100
DAILY_AMETISTA = 2

MSG_COOLDOWN = 60  # segundos
MSG_DIMA_MIN = 5
MSG_DIMA_MAX = 15

ROLL_CUSTO = 5  # ametista por giro

# banner da loja. padrao embutido, mas link de cdn expira:
# quando cair, bota o link novo no env que ele prevalece.
LOJA_BANNER_URL = os.getenv(
    "LOJA_BANNER_URL",
    "https://cdn.discordapp.com/attachments/1017344173843693628/1559204744256294932/image.png?ex=6ace3a13&is=6acce893&hm=5dd8661e05ae3737d4754eb4e73ab16dd9b12e337f7ba6808785d9da5860b046&",
)

# ─── auras (id -> nome, preço em ametista, descrição) ───
AURAS = {
    "brisa":      {"nome": "brisa do lago",         "preco": 10,  "desc": "aura inicial do lago"},
    "musgo":      {"nome": "manto de musgo",        "preco": 25,  "desc": "camuflagem tranquila"},
    "profundeza": {"nome": "olhar das profundezas", "preco": 50,  "desc": "o fundo do lago te observa"},
    "dourada":    {"nome": "escama dourada",        "preco": 100, "desc": "brilho raro de player antigo"},
    "ancestral":  {"nome": "presença ancestral",    "preco": 200, "desc": "o lago inteiro respeita"},
}

# ─── axolotls colecionáveis (gacha, peso soma 100) ───
# bruxinho e demonio tem peso 0: nunca saem no giro, so
# comprando com doces ou na caixa rara. peso 0 no
# random.choices nunca e sorteado.
AXOLOTLS = {
    "bebe":      {"nome": "bebê axolotl",       "rar": "comum",    "peso": 25},
    "rosa":      {"nome": "axolotl rosa",       "rar": "comum",    "peso": 16},
    "amarelo":   {"nome": "axolotl amarelo",    "rar": "comum",    "peso": 10},
    "verde":     {"nome": "axolotl verde",      "rar": "comum",    "peso": 10},
    "branco":    {"nome": "axolotl branco",     "rar": "comum",    "peso": 8},
    "musgo":     {"nome": "axolotl de musgo",   "rar": "incomum",  "peso": 8},
    "azul":      {"nome": "axolotl azul",       "rar": "incomum",  "peso": 5},
    "preto":     {"nome": "axolotl preto",      "rar": "incomum",  "peso": 4},
    "dourado":   {"nome": "axolotl dourado",    "rar": "raro",     "peso": 5},
    "cristal":   {"nome": "axolotl de cristal", "rar": "raro",     "peso": 4},
    "toxico":    {"nome": "axolotl tóxico",     "rar": "épico",    "peso": 2},
    "cosmico":   {"nome": "axolotl cósmico",    "rar": "épico",    "peso": 1.5},
    "abissal":   {"nome": "axolotl abissal",    "rar": "épico",    "peso": 1},
    "ancestral": {"nome": "axolotl ancestral",  "rar": "lendário", "peso": 0.3},
    "bugado":    {"nome": "axolotl bugado",     "rar": "lendário", "peso": 0.1},
    "roxo":      {"nome": "axolotl roxo",       "rar": "lendário", "peso": 0.1},
    "bruxinho":  {"nome": "axolotl bruxinho",   "rar": "lendário", "peso": 0},
    "demonio":   {"nome": "axolotl demônio",    "rar": "lendário", "peso": 0},
}

# ids antigos renomeados: quem ja tem no banco continua vendo o nome certo.
ALIAS_AXOLOTL = {"glitch": "bugado"}

# ─── loja de doces (id -> nome, preço em doces, descrição) ───
DOCES_LOJA = {
    "ametista1": {"nome": "1 ametista",       "preco": 20,  "desc": "doces derretidos viram ametista"},
    "dima50":    {"nome": "50 diamantes",     "preco": 30,  "desc": "pescados no fundo do lago"},
    "bruxinho":  {"nome": "axolotl bruxinho", "preco": 300, "desc": "exclusivo de halloween, lendário"},
    "demonio":   {"nome": "axolotl demônio",  "preco": 666, "desc": "o preço do lago, lendário"},
}

# ─── caixas (loot box: 3 axolotls por abertura) ───
CAIXA_CUSTO = 150       # diamantes pela caixa comum
CAIXA_RARA_CUSTO = 15   # ametista pela caixa rara

# pool da caixa rara: so de incomum pra cima (soma 100).
POOL_RARO = {
    "musgo":     10,
    "dourado":   13,
    "cristal":   11,
    "toxico":    12,
    "cosmico":   10,
    "azul":      8,
    "preto":     7,
    "abissal":   10,
    "ancestral": 8,
    "bruxinho":  5,
    "bugado":    4,
    "roxo":      1,
    "demonio":   1,
}

COR_RAR = {
    "comum": visual.TEXT_DIM,
    "incomum": visual.SECONDARY,
    "raro": visual.INFO,
    "épico": visual.PRIMARY,
    "lendário": visual.WARNING,
}

# opções de aura pros slash (nome bonito -> id).
_ESCOLHAS_AURA = [
    app_commands.Choice(name=info["nome"], value=aid) for aid, info in AURAS.items()
]

# tudo que o /buy vende: auras + itens de doces.
_ESCOLHAS_BUY = _ESCOLHAS_AURA + [
    app_commands.Choice(name=info["nome"], value=iid) for iid, info in DOCES_LOJA.items()
]


def _sortear_axolotl() -> str:
    ids = list(AXOLOTLS)
    pesos = [AXOLOTLS[i]["peso"] for i in ids]
    return random.choices(ids, weights=pesos, k=1)[0]


def _sortear_raro() -> str:
    """1 axolotl do pool da caixa rara (sem comum)."""
    ids = list(POOL_RARO)
    pesos = [POOL_RARO[i] for i in ids]
    return random.choices(ids, weights=pesos, k=1)[0]


def _abrir_caixa(sorteio) -> list[str]:
    """abre 1 caixa: 3 sorteios com a funcao dada."""
    return [sorteio() for _ in range(3)]


CAIXA_BUFF_SEG = 30 * 60  # 30min de 2x


async def _bonus_caixa(user_id: int, rara: bool) -> list[str]:
    """sorteia o bonus da caixa: moeda e/ou buff 2x. devolve linhas pro embed."""
    linhas = []
    if rara:
        if random.random() < 0.30:
            qtd = random.randint(2, 4)
            await asyncio.to_thread(data.adicionar_ametista, user_id, qtd)
            linhas.append(f"bonus: **+{qtd}** {visual.AMETHYST}!")
        if random.random() < 0.10:
            await asyncio.to_thread(data.dar_buff, user_id, "dima2", CAIXA_BUFF_SEG)
            linhas.append("bonus: **2x diamantes** por 30min!")
        if random.random() < 0.10:
            await asyncio.to_thread(data.dar_buff, user_id, "xp2", CAIXA_BUFF_SEG)
            linhas.append("bonus: **2x xp** por 30min!")
    else:
        if random.random() < 0.30:
            qtd = random.randint(40, 80)
            await asyncio.to_thread(data.adicionar_diamantes, user_id, qtd)
            linhas.append(f"bonus: **+{qtd}** {visual.DIAMANTE}!")
        if random.random() < 0.08:
            await asyncio.to_thread(data.dar_buff, user_id, "dima2", CAIXA_BUFF_SEG)
            linhas.append("bonus: **2x diamantes** por 30min!")
        if random.random() < 0.08:
            await asyncio.to_thread(data.dar_buff, user_id, "xp2", CAIXA_BUFF_SEG)
            linhas.append("bonus: **2x xp** por 30min!")
    return linhas


def _texto_buffs(buffs: dict) -> str:
    """ex: {'xp2': 700} -> **2x xp** (11min). vazio se sem buff."""
    nomes = {"xp2": "2x xp", "dima2": "2x dima"}

    def fmt(s: int) -> str:
        return f"{s // 60}min" if s >= 60 else f"{s}s"

    return " · ".join(f"**{nomes.get(t, t)}** ({fmt(s)})" for t, s in buffs.items() if s > 0)


def _embed_saldo(
    membro: discord.Member,
    dima: int,
    amet: int,
    aura_id: str | None,
    total_axo: int,
    buffs: dict | None = None,
) -> discord.Embed:
    aura_nome = AURAS[aura_id]["nome"] if aura_id in AURAS else "nenhuma"
    embed = discord.Embed(
        title=f"{visual.AXOLOTL} saldo de {membro.display_name}",
        color=visual.PRIMARY,
    )
    embed.add_field(name=f"{visual.DIAMANTE} diamantes", value=str(dima), inline=True)
    embed.add_field(name=f"{visual.AMETHYST} ametista", value=str(amet), inline=True)
    embed.add_field(name="aura", value=aura_nome, inline=True)
    embed.add_field(name=f"{visual.AXOLOTL} axolotls", value=str(total_axo), inline=True)
    texto_buffs = _texto_buffs(buffs or {})
    if texto_buffs:
        embed.add_field(name="⚡ buffs", value=texto_buffs, inline=False)
    embed.set_thumbnail(url=membro.display_avatar.url)
    embed.set_footer(text=visual.FOOTER)
    return embed


async def _pagar_e_sortear(user_id: int, rara: bool) -> list[str] | None:
    """cobra a caixa e devolve os 3 ids. None se sem saldo."""
    if rara:
        _, amet, _ = await asyncio.to_thread(data.buscar_saldo, user_id)
        if amet < CAIXA_RARA_CUSTO:
            return None
        await asyncio.to_thread(data.adicionar_ametista, user_id, -CAIXA_RARA_CUSTO)
        itens = _abrir_caixa(_sortear_raro)
    else:
        dima, _, _ = await asyncio.to_thread(data.buscar_saldo, user_id)
        if dima < CAIXA_CUSTO:
            return None
        await asyncio.to_thread(data.adicionar_diamantes, user_id, -CAIXA_CUSTO)
        itens = _abrir_caixa(_sortear_axolotl)
    for aid in itens:
        await asyncio.to_thread(data.adicionar_axolotl, user_id, aid)
    return itens


async def _animar_caixa(
    edit,
    titulo: str,
    itens: list[str],
    view: discord.ui.View | None,
    bonus: list[str] | None = None,
):
    """revela os 3 um por vez (~1s cada). `edit` recebe embed/view."""
    await asyncio.sleep(0.9)
    for n in (1, 2):
        await edit(embed=Economia._embed_parcial(titulo, itens, n))
        await asyncio.sleep(0.9)
    await edit(embed=Economia._embed_caixa(titulo, itens, bonus), view=view)


class CaixaView(discord.ui.View):
    """botao abrir outra. so quem abriu usa. expira em 2min."""

    def __init__(self, dono_id: int, rara: bool):
        super().__init__(timeout=120)
        self.dono_id = dono_id
        self.rara = rara

    @discord.ui.button(label="abrir outra", emoji="🎁", style=discord.ButtonStyle.primary)
    async def outra(self, interaction: discord.Interaction, _: discord.ui.Button):
        if interaction.user.id != self.dono_id:
            await interaction.response.send_message(
                "só quem abriu a caixa usa esse botão!", ephemeral=True
            )
            return
        itens = await _pagar_e_sortear(self.dono_id, self.rara)
        if itens is None:
            moeda = visual.AMETHYST if self.rara else visual.DIAMANTE
            custo = CAIXA_RARA_CUSTO if self.rara else CAIXA_CUSTO
            await interaction.response.send_message(
                f"sem saldo! a caixa custa **{custo}** {moeda}.", ephemeral=True
            )
            return
        moeda = visual.AMETHYST if self.rara else visual.DIAMANTE
        nome = "caixa rara" if self.rara else "caixa"
        titulo = f"{moeda} você abriu outra {nome}!"
        bonus = await _bonus_caixa(self.dono_id, self.rara)
        await interaction.response.send_message(
            embed=Economia._embed_parcial(titulo, itens, 0)
        )
        await _animar_caixa(interaction.edit_original_response, titulo, itens, self, bonus)


# emoji de cada secao da loja.
LOJA_EMOJIS = {
    "Auras": "✨",
    "Doces": "🍬",
    "Caixas": "🎁",
}


def _embed_loja_capa() -> discord.Embed:
    """capa da loja: banner + botoes por categoria."""
    embed = discord.Embed(
        title=f"{visual.AXOLOTL} loja do lago",
        description=(
            "tudo que o lago tem pra vender hoje.\n"
            "escolhe uma categoria aqui embaixo."
        ),
        color=visual.PRIMARY,
    )
    if LOJA_BANNER_URL:
        embed.set_image(url=LOJA_BANNER_URL)
    embed.set_footer(text=visual.FOOTER)
    return embed


def _embed_loja_secao(titulo: str, descricao: str, saldo: str, rodape: str) -> discord.Embed:
    """uma categoria so: titulo + itens + saldo + banner."""
    emoji = LOJA_EMOJIS.get(titulo, "")
    nome = f"{emoji} {titulo}".strip()
    embed = discord.Embed(
        title=f"{visual.AXOLOTL} {nome}",
        description=descricao,
        color=visual.PRIMARY,
    )
    embed.add_field(name="seu saldo", value=saldo, inline=False)
    if LOJA_BANNER_URL:
        embed.set_image(url=LOJA_BANNER_URL)
    embed.set_footer(text=f"{rodape} • {visual.FOOTER}")
    return embed


def _secoes_loja(
    dima: int, amet: int, aura: str | None, minhas: set, doces: int, barra: str
) -> list[tuple[str, discord.Embed]]:
    """3 secoes prontas: [(titulo, embed)]. `barra` e `>` ou `/` pros exemplos."""
    saldo = f"**{dima}** {visual.DIAMANTE} • **{amet}** {visual.AMETHYST} • **{doces}** 🍬"
    linhas_auras = []
    for aid, info in AURAS.items():
        dono = "(sua)" if aid in minhas else ""
        equip = " (equipada)" if aura == aid else ""
        linhas_auras.append(
            f"`{aid}` — **{info['nome']}** — **{info['preco']}** {visual.AMETHYST} {dono}{equip}\n└ {info['desc']}"
        )
    linhas_doces = []
    for iid, info in DOCES_LOJA.items():
        linhas_doces.append(
            f"`{iid}` — **{info['nome']}** — **{info['preco']}** 🍬\n└ {info['desc']}"
        )
    texto_caixas = (
        f"`{barra}roll` — **{ROLL_CUSTO}** {visual.AMETHYST} por giro. sorteia 1 axolotl.\n\n"
        f"`{barra}box` — **{CAIXA_CUSTO}** {visual.DIAMANTE}: 3 axolotls do pool normal.\n\n"
        f"`{barra}caixarara` — **{CAIXA_RARA_CUSTO}** {visual.AMETHYST}: 3 axolotls raros "
        "(sem comum, com chance de roxo, bruxinho e demônio)."
    )
    return [
        (
            "Auras",
            _embed_loja_secao(
                "Auras",
                "poder passivo pro teu perfil.\n\n" + "\n\n".join(linhas_auras),
                saldo,
                f"{barra}buy <id> compra aura • {barra}equipar <id>",
            ),
        ),
        (
            "Doces",
            _embed_loja_secao(
                "Doces",
                "troca os doces do halloween.\n\n" + "\n\n".join(linhas_doces),
                saldo,
                f"{barra}buy <id> troca com doces",
            ),
        ),
        (
            "Caixas",
            _embed_loja_secao(
                "Caixas",
                "loot box: 3 axolotls por abertura.\n\n" + texto_caixas,
                saldo,
                f"{barra}box abre • {barra}caixarara abre a rara",
            ),
        ),
    ]


class LojaView(discord.ui.View):
    """botoes por categoria da loja. expira em 3min."""

    def __init__(self, secoes: list[tuple[str, discord.Embed]]):
        super().__init__(timeout=180)
        self._mapa = dict(secoes)
        for titulo, _embed in secoes:
            self.add_item(self._botao(titulo))
        tudo = discord.ui.Button(
            label="tudo",
            emoji="📋",
            style=discord.ButtonStyle.primary,
            custom_id="loja:tudo",
        )

        async def mostrar_tudo(interaction: discord.Interaction):
            embed = discord.Embed(
                title=f"{visual.AXOLOTL} loja do lago",
                color=visual.PRIMARY,
            )
            for titulo, sec in self._mapa.items():
                embed.add_field(name=titulo, value=sec.description, inline=False)
            if LOJA_BANNER_URL:
                embed.set_image(url=LOJA_BANNER_URL)
            embed.set_footer(text=visual.FOOTER)
            await interaction.response.edit_message(embed=embed, view=self)

        tudo.callback = mostrar_tudo
        self.add_item(tudo)
        inicio = discord.ui.Button(
            label="início",
            emoji="🏠",
            style=discord.ButtonStyle.secondary,
            custom_id="loja:inicio",
        )

        async def voltar(interaction: discord.Interaction):
            await interaction.response.edit_message(embed=_embed_loja_capa(), view=self)

        inicio.callback = voltar
        self.add_item(inicio)

    def _botao(self, titulo: str) -> discord.ui.Button:
        botao = discord.ui.Button(
            label=titulo,
            emoji=LOJA_EMOJIS.get(titulo),
            style=discord.ButtonStyle.secondary,
            custom_id=f"loja:cat:{titulo}",
        )

        async def mostrar(interaction: discord.Interaction, alvo=titulo):
            await interaction.response.edit_message(embed=self._mapa[alvo], view=self)

        botao.callback = mostrar
        return botao


class Economia(commands.Cog, name="Economia"):
    """diamantes, ametista, auras e coleção de axolotls."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.cooldown: dict[int, float] = {}

    # ─── farm passivo por mensagem ───
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        agora = discord.utils.utcnow().timestamp()
        if agora - self.cooldown.get(message.author.id, 0) < MSG_COOLDOWN:
            return
        self.cooldown[message.author.id] = agora
        ganho = random.randint(MSG_DIMA_MIN, MSG_DIMA_MAX)
        if await asyncio.to_thread(data.buff_ativo, message.author.id, "dima2"):
            ganho *= 2
        await asyncio.to_thread(data.adicionar_diamantes, message.author.id, ganho)

    # ─── >saldo / /saldo ───
    @commands.command(name="saldo")
    async def saldo(self, ctx: commands.Context, membro: discord.Member = None):
        """veja seus diamantes, ametista, aura e coleção."""
        membro = membro or ctx.author
        # leituras independentes, roda junto.
        (dima, amet, aura), colecao, buffs = await asyncio.gather(
            asyncio.to_thread(data.buscar_saldo, membro.id),
            asyncio.to_thread(data.buscar_colecao, membro.id),
            asyncio.to_thread(data.buffs_ativos, membro.id),
        )
        total = sum(q for _, q in colecao)
        await ctx.send(embed=_embed_saldo(membro, dima, amet, aura, total, buffs))

    @app_commands.command(name="saldo", description="veja seus diamantes, ametista, aura e coleção.")
    async def saldo_slash(self, interaction: discord.Interaction):
        # leituras independentes, roda junto.
        (dima, amet, aura), colecao, buffs = await asyncio.gather(
            asyncio.to_thread(data.buscar_saldo, interaction.user.id),
            asyncio.to_thread(data.buscar_colecao, interaction.user.id),
            asyncio.to_thread(data.buffs_ativos, interaction.user.id),
        )
        total = sum(q for _, q in colecao)
        membro = interaction.user
        await interaction.response.send_message(
            embed=_embed_saldo(membro, dima, amet, aura, total, buffs)
        )

    # ─── >daily / /daily ───
    async def _daily(self, user_id: int) -> tuple[bool, int, int]:
        hoje = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return await asyncio.to_thread(
            data.tentar_daily, user_id, DAILY_DIAMANTES, DAILY_AMETISTA, hoje
        )

    @commands.command(name="daily")
    async def daily(self, ctx: commands.Context):
        """resgate diário: diamantes + ametista. 1x por dia."""
        ok, dima, amet = await self._daily(ctx.author.id)
        if not ok:
            await ctx.send(
                f"{visual.AXOLOTL} {ctx.author.mention} você já resgatou hoje! volta amanhã."
            )
            return
        await ctx.send(
            f"{visual.AXOLOTL} {ctx.author.mention} resgatou "
            f"**{DAILY_DIAMANTES}** {visual.DIAMANTE} + **{DAILY_AMETISTA}** {visual.AMETHYST}!"
        )

    @app_commands.command(name="daily", description="resgate diário: diamantes + ametista.")
    async def daily_slash(self, interaction: discord.Interaction):
        ok, _, _ = await self._daily(interaction.user.id)
        if not ok:
            await interaction.response.send_message(
                f"{visual.AXOLOTL} você já resgatou hoje! volta amanhã.",
                ephemeral=True,
            )
            return
        await interaction.response.send_message(
            f"{visual.AXOLOTL} resgatado: **{DAILY_DIAMANTES}** {visual.DIAMANTE} + "
            f"**{DAILY_AMETISTA}** {visual.AMETHYST}!"
        )

    # ─── >pay ───
    @commands.command(name="pay")
    async def pay(self, ctx: commands.Context, membro: discord.Member = None, qtd: int = 0):
        """transfira diamantes pra outro membro. ex: `>pay @ana 50`."""
        if membro is None or qtd <= 0:
            await ctx.send(f"{visual.AXOLOTL} uso: `>pay @membro quantia` (mínimo 1).")
            return
        if membro.bot:
            await ctx.send(f"{visual.AXOLOTL} não dá pra pagar pra bot.")
            return
        if membro.id == ctx.author.id:
            await ctx.send(f"{visual.AXOLOTL} não dá pra pagar pra você mesmo.")
            return
        ok, _, _ = await asyncio.to_thread(
            data.transferir_diamantes, ctx.author.id, membro.id, qtd
        )
        if not ok:
            await ctx.send(
                f"{visual.AXOLOTL} {ctx.author.mention} saldo insuficiente!"
            )
            return
        await ctx.send(
            f"{visual.DIAMANTE} {ctx.author.mention} enviou **{qtd}** diamantes pra {membro.mention}!"
        )

    # ─── >dar (admin) ───
    @commands.command(name="dar")
    @commands.has_permissions(administrator=True)
    async def dar(self, ctx: commands.Context, membro: discord.Member = None, moeda: str = "", qtd: int = 0):
        """[admin] dá moedas. ex: `>dar @ana diamantes 100` ou `>dar @ana ametista 5`."""
        moeda = moeda.lower()
        if membro is None or qtd <= 0 or moeda not in ("diamantes", "diamante", "dima", "ametista", "amet"):
            await ctx.send(
                f"{visual.AXOLOTL} uso: `>dar @membro diamantes|ametista quantia`."
            )
            return
        if moeda in ("diamantes", "diamante", "dima"):
            total = await asyncio.to_thread(data.adicionar_diamantes, membro.id, qtd)
            await ctx.send(
                f"{visual.DIAMANTE} {membro.mention} recebeu **{qtd}** diamantes! (total: **{total}**)"
            )
        else:
            total = await asyncio.to_thread(data.adicionar_ametista, membro.id, qtd)
            await ctx.send(
                f"{visual.AMETHYST} {membro.mention} recebeu **{qtd}** ametista! (total: **{total}**)"
            )

    # ─── >loja ───
    @commands.command(name="loja")
    async def loja(self, ctx: commands.Context):
        """loja do lago por categoria: auras, doces e caixas."""
        # leituras independentes, roda junto.
        (dima, amet, aura), minhas, doces = await asyncio.gather(
            asyncio.to_thread(data.buscar_saldo, ctx.author.id),
            asyncio.to_thread(data.auras_usuario, ctx.author.id),
            asyncio.to_thread(data.buscar_doces, ctx.author.id),
        )
        secoes = _secoes_loja(dima, amet, aura, set(minhas), doces, ">")
        await ctx.send(embed=_embed_loja_capa(), view=LojaView(secoes))

    # ─── >buy ───
    @commands.command(name="buy")
    async def buy(self, ctx: commands.Context, item_id: str = None):
        """compra aura com ametista ou item com doces. ex: `>buy brisa`, `>buy dima50`."""
        if item_id is None:
            await ctx.send(f"{visual.AXOLOTL} uso: `>buy <id>` — veja os ids com `>loja`.")
            return
        item_id = item_id.lower()
        if item_id in DOCES_LOJA:
            await self._buy_doces(ctx, item_id)
            return
        if item_id not in AURAS:
            await ctx.send(
                f"{visual.AXOLOTL} item inválido! veja com `>loja`. opções: "
                + ", ".join(f"`{k}`" for k in list(AURAS) + list(DOCES_LOJA))
            )
            return
        aura_id = item_id
        if await asyncio.to_thread(data.tem_aura, ctx.author.id, aura_id):
            await ctx.send(f"{visual.AXOLOTL} você já tem essa aura! use `>equipar {aura_id}`.")
            return
        _, amet, _ = await asyncio.to_thread(data.buscar_saldo, ctx.author.id)
        preco = AURAS[aura_id]["preco"]
        if amet < preco:
            await ctx.send(
                f"{visual.AMETHYST} faltam **{preco - amet}** ametista pra **{AURAS[aura_id]['nome']}**!"
            )
            return
        await asyncio.to_thread(data.adicionar_ametista, ctx.author.id, -preco)
        await asyncio.to_thread(data.dar_aura, ctx.author.id, aura_id)
        await asyncio.to_thread(data.equipar_aura, ctx.author.id, aura_id)
        await ctx.send(
            f"{visual.AXOLOTL} {ctx.author.mention} comprou e equipou **{AURAS[aura_id]['nome']}**!"
        )

    async def _trocar_doces(self, user_id: int, item_id: str) -> str:
        """troca doces pelo item. devolve a msg pronta. vale pro `>` e pro `/`."""
        info = DOCES_LOJA[item_id]
        ok, _ = await asyncio.to_thread(data.gastar_doces, user_id, info["preco"])
        if not ok:
            return f"🍬 faltam doces pra **{info['nome']}**! custa **{info['preco']}** 🍬."
        if item_id == "ametista1":
            await asyncio.to_thread(data.adicionar_ametista, user_id, 1)
            return f"🍬 trocou **{info['preco']}** doces por **1** {visual.AMETHYST}!"
        if item_id == "dima50":
            await asyncio.to_thread(data.adicionar_diamantes, user_id, 50)
            return f"🍬 trocou **{info['preco']}** doces por **50** {visual.DIAMANTE}!"
        qtd = await asyncio.to_thread(data.adicionar_axolotl, user_id, item_id)
        axo = AXOLOTLS[item_id]
        return (
            f"🍬 trocou **{info['preco']}** doces por **{axo['nome']}** ({axo['rar']})! "
            f"você tem **{qtd}x** esse."
        )

    async def _buy_doces(self, ctx: commands.Context, item_id: str):
        """atalho do prefixo pra troca com doces."""
        msg = await self._trocar_doces(ctx.author.id, item_id)
        await ctx.send(f"{visual.AXOLOTL} {ctx.author.mention} {msg}")

    # ─── >equipar / >auras ───
    @commands.command(name="equipar", aliases=["aura"])
    async def equipar(self, ctx: commands.Context, aura_id: str = None):
        """equipa uma aura que você já tem. ex: `>equipar brisa`."""
        if aura_id is None:
            await ctx.send(f"{visual.AXOLOTL} uso: `>equipar <id>` — veja as suas com `>auras`.")
            return
        aura_id = aura_id.lower()
        if aura_id not in AURAS:
            await ctx.send(f"{visual.AXOLOTL} essa aura não existe! veja com `>loja`.")
            return
        if not await asyncio.to_thread(data.tem_aura, ctx.author.id, aura_id):
            await ctx.send(f"{visual.AXOLOTL} você ainda não tem essa aura! compre com `>buy {aura_id}`.")
            return
        await asyncio.to_thread(data.equipar_aura, ctx.author.id, aura_id)
        await ctx.send(f"{ctx.author.mention} equipou **{AURAS[aura_id]['nome']}**!")

    @commands.command(name="auras")
    async def auras(self, ctx: commands.Context):
        """lista as auras que você possui."""
        _, _, equipada = await asyncio.to_thread(data.buscar_saldo, ctx.author.id)
        posses = await asyncio.to_thread(data.auras_usuario, ctx.author.id)
        if not posses:
            await ctx.send(f"{visual.AXOLOTL} você ainda não tem auras! veja com `>loja`.")
            return
        linhas = []
        for aid in posses:
            marca = " (equipada)" if aid == equipada else ""
            linhas.append(f"• **{AURAS[aid]['nome']}** (`{aid}`){marca}")
        await ctx.send("suas auras:\n" + "\n".join(linhas))

    # ─── >roll ───
    @commands.command(name="roll")
    async def roll(self, ctx: commands.Context):
        """gira a coleção: 5 ametista = 1 axolotl aleatório."""
        _, amet, _ = await asyncio.to_thread(data.buscar_saldo, ctx.author.id)
        if amet < ROLL_CUSTO:
            await ctx.send(
                f"{visual.AMETHYST} você precisa de **{ROLL_CUSTO}** ametista pra girar! "
                f"(você tem **{amet}** — pegue com `>daily`)"
            )
            return
        await asyncio.to_thread(data.adicionar_ametista, ctx.author.id, -ROLL_CUSTO)
        sorteado = _sortear_axolotl()
        qtd = await asyncio.to_thread(data.adicionar_axolotl, ctx.author.id, sorteado)
        info = AXOLOTLS[sorteado]
        embed = discord.Embed(
            title=f"{visual.AXOLOTL} {info['nome']}!",
            description=(
                f"{ctx.author.mention} tirou um **{info['nome']}** ({info['rar']})!\n"
                f"você tem **{qtd}x** esse."
            ),
            color=COR_RAR.get(info["rar"], visual.PRIMARY),
        )
        embed.set_footer(text=visual.FOOTER)
        await ctx.send(embed=embed)

    @app_commands.command(name="roll", description="gire 5 ametista e tire um axolotl aleatório.")
    async def roll_slash(self, interaction: discord.Interaction):
        _, amet, _ = await asyncio.to_thread(data.buscar_saldo, interaction.user.id)
        if amet < ROLL_CUSTO:
            await interaction.response.send_message(
                f"{visual.AMETHYST} você precisa de **{ROLL_CUSTO}** ametista pra girar!",
                ephemeral=True,
            )
            return
        await asyncio.to_thread(data.adicionar_ametista, interaction.user.id, -ROLL_CUSTO)
        sorteado = _sortear_axolotl()
        qtd = await asyncio.to_thread(data.adicionar_axolotl, interaction.user.id, sorteado)
        info = AXOLOTLS[sorteado]
        embed = discord.Embed(
            title=f"{visual.AXOLOTL} {info['nome']}!",
            description=f"você tirou **{info['nome']}** ({info['rar']})! você tem **{qtd}x**.",
            color=COR_RAR.get(info["rar"], visual.PRIMARY),
        )
        embed.set_footer(text=visual.FOOTER)
        await interaction.response.send_message(embed=embed)

    # ─── caixas ───
    @staticmethod
    def _embed_parcial(titulo: str, itens: list[str], revelados: int) -> discord.Embed:
        """suspense da abertura: revelados a mostra, resto ❓."""
        linhas = []
        for j, aid in enumerate(itens):
            if j < revelados:
                info = AXOLOTLS.get(aid, {"nome": aid, "rar": "?"})
                linhas.append(f"• **{info['nome']}** ({info['rar']})")
            else:
                linhas.append("• ❓ ???")
        embed = discord.Embed(
            title=titulo,
            description="\n".join(linhas),
            color=visual.PRIMARY,
        )
        embed.set_footer(text=visual.FOOTER)
        return embed

    @staticmethod
    def _embed_caixa(
        titulo: str, itens: list[str], bonus: list[str] | None = None
    ) -> discord.Embed:
        """embed da caixa aberta: os 3 axolotls + bonus. cor = raridade mais alta."""
        ordem = {"comum": 0, "incomum": 1, "raro": 2, "épico": 3, "lendário": 4}
        melhor = "comum"
        linhas = []
        for aid in itens:
            info = AXOLOTLS.get(aid, {"nome": aid, "rar": "?"})
            linhas.append(f"• **{info['nome']}** ({info['rar']})")
            if ordem.get(info["rar"], 0) > ordem.get(melhor, 0):
                melhor = info["rar"]
        if bonus:
            linhas.append("")
            linhas.extend(bonus)
        embed = discord.Embed(
            title=titulo,
            description="\n".join(linhas),
            color=COR_RAR.get(melhor, visual.PRIMARY),
        )
        embed.set_footer(text=visual.FOOTER)
        return embed

    # ─── >box ───
    @commands.command(name="box", aliases=["caixa"])
    async def box(self, ctx: commands.Context):
        """abre a box comum: 150 diamantes = 3 axolotls do pool normal."""
        itens = await _pagar_e_sortear(ctx.author.id, False)
        if itens is None:
            dima, _, _ = await asyncio.to_thread(data.buscar_saldo, ctx.author.id)
            await ctx.send(
                f"{visual.DIAMANTE} a caixa custa **{CAIXA_CUSTO}** diamantes! "
                f"(você tem **{dima}**)"
            )
            return
        titulo = f"{visual.DIAMANTE} {ctx.author.display_name} abriu a caixa!"
        bonus = await _bonus_caixa(ctx.author.id, False)
        msg = await ctx.send(embed=self._embed_parcial(titulo, itens, 0))
        await _animar_caixa(msg.edit, titulo, itens, CaixaView(ctx.author.id, False), bonus)

    @app_commands.command(name="box", description="abre a box comum: 150 diamantes = 3 axolotls.")
    async def box_slash(self, interaction: discord.Interaction):
        """versão slash do >box."""
        itens = await _pagar_e_sortear(interaction.user.id, False)
        if itens is None:
            await interaction.response.send_message(
                f"{visual.DIAMANTE} a caixa custa **{CAIXA_CUSTO}** diamantes!",
                ephemeral=True,
            )
            return
        titulo = f"{visual.DIAMANTE} você abriu a caixa!"
        bonus = await _bonus_caixa(interaction.user.id, False)
        await interaction.response.send_message(embed=self._embed_parcial(titulo, itens, 0))
        await _animar_caixa(
            interaction.edit_original_response,
            titulo,
            itens,
            CaixaView(interaction.user.id, False),
            bonus,
        )

    # ─── >caixarara ───
    @commands.command(name="caixarara")
    async def caixarara(self, ctx: commands.Context):
        """abre a caixa rara: 15 ametista = 3 axolotls sem comum (com roxo, bruxinho e demônio)."""
        itens = await _pagar_e_sortear(ctx.author.id, True)
        if itens is None:
            _, amet, _ = await asyncio.to_thread(data.buscar_saldo, ctx.author.id)
            await ctx.send(
                f"{visual.AMETHYST} a caixa rara custa **{CAIXA_RARA_CUSTO}** ametista! "
                f"(você tem **{amet}** — pegue com `>daily`)"
            )
            return
        titulo = f"{visual.AMETHYST} {ctx.author.display_name} abriu a caixa rara!"
        bonus = await _bonus_caixa(ctx.author.id, True)
        msg = await ctx.send(embed=self._embed_parcial(titulo, itens, 0))
        await _animar_caixa(msg.edit, titulo, itens, CaixaView(ctx.author.id, True), bonus)

    @app_commands.command(name="caixarara", description="abre a caixa rara: 15 ametista = 3 axolotls raros.")
    async def caixarara_slash(self, interaction: discord.Interaction):
        """versão slash do >caixarara."""
        itens = await _pagar_e_sortear(interaction.user.id, True)
        if itens is None:
            await interaction.response.send_message(
                f"{visual.AMETHYST} a caixa rara custa **{CAIXA_RARA_CUSTO}** ametista!",
                ephemeral=True,
            )
            return
        titulo = f"{visual.AMETHYST} você abriu a caixa rara!"
        bonus = await _bonus_caixa(interaction.user.id, True)
        await interaction.response.send_message(embed=self._embed_parcial(titulo, itens, 0))
        await _animar_caixa(
            interaction.edit_original_response,
            titulo,
            itens,
            CaixaView(interaction.user.id, True),
            bonus,
        )

    # ─── >colecao ───
    @commands.command(name="colecao")
    async def colecao(self, ctx: commands.Context, membro: discord.Member = None):
        """mostra sua coleção de axolotls (ou a de outro membro)."""
        membro = membro or ctx.author
        itens = await asyncio.to_thread(data.buscar_colecao, membro.id)
        if not itens:
            await ctx.send(
                f"{visual.AXOLOTL} {membro.display_name} ainda não tem axolotls! use `>roll`."
            )
            return
        linhas = []
        for aid, qtd in itens:
            aid = ALIAS_AXOLOTL.get(aid, aid)
            info = AXOLOTLS.get(aid, {"nome": aid, "rar": "?"})
            linhas.append(f"• **{info['nome']}** ({info['rar']}) — **{qtd}x**")
        embed = discord.Embed(
            title=f"{visual.AXOLOTL} coleção de {membro.display_name}",
            description="\n".join(linhas),
            color=visual.PRIMARY,
        )
        embed.set_footer(text=f"{len(itens)}/{len(AXOLOTLS)} espécies • {visual.FOOTER}")
        await ctx.send(embed=embed)

    # ─── >topdima ───
    @commands.command(name="topdima")
    async def topdima(self, ctx: commands.Context):
        """ranking dos mais ricos em diamantes."""
        ranking = await asyncio.to_thread(data.top_diamantes, 10)
        if not ranking:
            await ctx.send(f"{visual.AXOLOTL} ninguém tem diamantes ainda! use `>daily`.")
            return
        medalhas = [f"**{i}.**" for i in range(1, 11)]
        linhas = []
        for i, (uid, dima) in enumerate(ranking):
            membro = ctx.guild.get_member(uid) if ctx.guild else None
            nome = membro.display_name if membro else f"usuário {uid}"
            linhas.append(f"{medalhas[i]} {nome} — **{dima}** {visual.DIAMANTE}")
        embed = discord.Embed(
            title=f"{visual.DIAMANTE} top diamantes",
            description="\n".join(linhas),
            color=visual.WARNING,
        )
        embed.set_footer(text=visual.FOOTER)
        await ctx.send(embed=embed)

    # ─── /pay ───
    @app_commands.command(name="pay", description="transfira diamantes pra outro membro.")
    @app_commands.describe(membro="quem recebe", qtd="quantidade (mínimo 1)")
    async def pay_slash(
        self, interaction: discord.Interaction, membro: discord.Member, qtd: int
    ):
        """versão slash do >pay."""
        autor = interaction.user
        if qtd <= 0:
            await interaction.response.send_message(
                f"{visual.AXOLOTL} a quantia mínima é 1.", ephemeral=True
            )
            return
        if membro.bot:
            await interaction.response.send_message(
                f"{visual.AXOLOTL} não dá pra pagar pra bot.", ephemeral=True
            )
            return
        if membro.id == autor.id:
            await interaction.response.send_message(
                f"{visual.AXOLOTL} não dá pra pagar pra você mesmo.", ephemeral=True
            )
            return
        ok, _, _ = await asyncio.to_thread(
            data.transferir_diamantes, autor.id, membro.id, qtd
        )
        if not ok:
            await interaction.response.send_message(
                f"{visual.AXOLOTL} saldo insuficiente!", ephemeral=True
            )
            return
        await interaction.response.send_message(
            f"{visual.DIAMANTE} {autor.mention} enviou **{qtd}** diamantes pra {membro.mention}!"
        )

    # ─── /dar (admin) ───
    @app_commands.command(name="dar", description="[admin] dá moedas pra um membro.")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(membro="quem recebe", moeda="qual moeda", qtd="quantidade")
    @app_commands.choices(moeda=[
        app_commands.Choice(name="diamantes", value="diamantes"),
        app_commands.Choice(name="ametista", value="ametista"),
    ])
    async def dar_slash(
        self,
        interaction: discord.Interaction,
        membro: discord.Member,
        moeda: str,
        qtd: int,
    ):
        """versão slash do >dar."""
        if qtd <= 0:
            await interaction.response.send_message(
                f"{visual.AXOLOTL} a quantia mínima é 1.", ephemeral=True
            )
            return
        if moeda == "diamantes":
            total = await asyncio.to_thread(data.adicionar_diamantes, membro.id, qtd)
            await interaction.response.send_message(
                f"{visual.DIAMANTE} {membro.mention} recebeu **{qtd}** diamantes! (total: **{total}**)"
            )
        else:
            total = await asyncio.to_thread(data.adicionar_ametista, membro.id, qtd)
            await interaction.response.send_message(
                f"{visual.AMETHYST} {membro.mention} recebeu **{qtd}** ametista! (total: **{total}**)"
            )

    # ─── /loja ───
    @app_commands.command(name="loja", description="loja do lago por categoria: auras, doces e caixas.")
    async def loja_slash(self, interaction: discord.Interaction):
        """versão slash do >loja."""
        user_id = interaction.user.id
        # leituras independentes, roda junto.
        (dima, amet, aura), minhas, doces = await asyncio.gather(
            asyncio.to_thread(data.buscar_saldo, user_id),
            asyncio.to_thread(data.auras_usuario, user_id),
            asyncio.to_thread(data.buscar_doces, user_id),
        )
        secoes = _secoes_loja(dima, amet, aura, set(minhas), doces, "/")
        await interaction.response.send_message(
            embed=_embed_loja_capa(), view=LojaView(secoes), ephemeral=True
        )

    # ─── /buy ───
    @app_commands.command(name="buy", description="compra aura com ametista ou item com doces.")
    @app_commands.describe(aura_id="o que comprar")
    @app_commands.choices(aura_id=_ESCOLHAS_BUY)
    async def buy_slash(self, interaction: discord.Interaction, aura_id: str):
        """versão slash do >buy."""
        user_id = interaction.user.id
        if aura_id in DOCES_LOJA:
            msg = await self._trocar_doces(user_id, aura_id)
            await interaction.response.send_message(f"{visual.AXOLOTL} {msg}")
            return
        if await asyncio.to_thread(data.tem_aura, user_id, aura_id):
            await interaction.response.send_message(
                f"{visual.AXOLOTL} você já tem essa aura! equipe com `/equipar`.",
                ephemeral=True,
            )
            return
        _, amet, _ = await asyncio.to_thread(data.buscar_saldo, user_id)
        preco = AURAS[aura_id]["preco"]
        if amet < preco:
            await interaction.response.send_message(
                f"{visual.AMETHYST} faltam **{preco - amet}** ametista pra **{AURAS[aura_id]['nome']}**!",
                ephemeral=True,
            )
            return
        await asyncio.to_thread(data.adicionar_ametista, user_id, -preco)
        await asyncio.to_thread(data.dar_aura, user_id, aura_id)
        await asyncio.to_thread(data.equipar_aura, user_id, aura_id)
        await interaction.response.send_message(
            f"{visual.AXOLOTL} você comprou e equipou **{AURAS[aura_id]['nome']}**!"
        )

    # ─── /equipar ───
    @app_commands.command(name="equipar", description="equipa uma aura que você já tem.")
    @app_commands.describe(aura_id="qual aura equipar")
    @app_commands.choices(aura_id=_ESCOLHAS_AURA)
    async def equipar_slash(self, interaction: discord.Interaction, aura_id: str):
        """versão slash do >equipar."""
        user_id = interaction.user.id
        if not await asyncio.to_thread(data.tem_aura, user_id, aura_id):
            await interaction.response.send_message(
                f"{visual.AXOLOTL} você ainda não tem essa aura! compre com `/buy`.",
                ephemeral=True,
            )
            return
        await asyncio.to_thread(data.equipar_aura, user_id, aura_id)
        await interaction.response.send_message(
            f"você equipou **{AURAS[aura_id]['nome']}**!"
        )

    # ─── /auras ───
    @app_commands.command(name="auras", description="lista as auras que você possui.")
    async def auras_slash(self, interaction: discord.Interaction):
        """versão slash do >auras."""
        user_id = interaction.user.id
        _, _, equipada = await asyncio.to_thread(data.buscar_saldo, user_id)
        posses = await asyncio.to_thread(data.auras_usuario, user_id)
        if not posses:
            await interaction.response.send_message(
                f"{visual.AXOLOTL} você ainda não tem auras! veja com `/loja`.",
                ephemeral=True,
            )
            return
        linhas = []
        for aid in posses:
            marca = " (equipada)" if aid == equipada else ""
            linhas.append(f"• **{AURAS[aid]['nome']}** (`{aid}`){marca}")
        await interaction.response.send_message(
            "suas auras:\n" + "\n".join(linhas), ephemeral=True
        )

    # ─── /colecao ───
    @app_commands.command(name="colecao", description="mostra a coleção de axolotls.")
    @app_commands.describe(membro="ver a coleção de outro membro (opcional)")
    async def colecao_slash(
        self, interaction: discord.Interaction, membro: discord.Member | None = None
    ):
        """versão slash do >colecao."""
        membro = membro or interaction.user
        itens = await asyncio.to_thread(data.buscar_colecao, membro.id)
        if not itens:
            await interaction.response.send_message(
                f"{visual.AXOLOTL} {membro.display_name} ainda não tem axolotls! use `/roll`.",
                ephemeral=True,
            )
            return
        linhas = []
        for aid, qtd in itens:
            aid = ALIAS_AXOLOTL.get(aid, aid)
            info = AXOLOTLS.get(aid, {"nome": aid, "rar": "?"})
            linhas.append(f"• **{info['nome']}** ({info['rar']}) — **{qtd}x**")
        embed = discord.Embed(
            title=f"{visual.AXOLOTL} coleção de {membro.display_name}",
            description="\n".join(linhas),
            color=visual.PRIMARY,
        )
        embed.set_footer(text=f"{len(itens)}/{len(AXOLOTLS)} espécies • {visual.FOOTER}")
        await interaction.response.send_message(embed=embed)

    # ─── /topdima ───
    @app_commands.command(name="topdima", description="ranking dos mais ricos em diamantes.")
    async def topdima_slash(self, interaction: discord.Interaction):
        """versão slash do >topdima."""
        ranking = await asyncio.to_thread(data.top_diamantes, 10)
        if not ranking:
            await interaction.response.send_message(
                f"{visual.AXOLOTL} ninguém tem diamantes ainda! use `/daily`.",
                ephemeral=True,
            )
            return
        medalhas = [f"**{i}.**" for i in range(1, 11)]
        linhas = []
        for i, (uid, dima) in enumerate(ranking):
            membro = interaction.guild.get_member(uid) if interaction.guild else None
            nome = membro.display_name if membro else f"usuário {uid}"
            linhas.append(f"{medalhas[i]} {nome} — **{dima}** {visual.DIAMANTE}")
        embed = discord.Embed(
            title=f"{visual.DIAMANTE} top diamantes",
            description="\n".join(linhas),
            color=visual.WARNING,
        )
        embed.set_footer(text=visual.FOOTER)
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Economia(bot))
