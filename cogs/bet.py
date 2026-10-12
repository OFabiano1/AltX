# isso aq e o axolotl bet: cassino so com moeda.
# ganha ou perde so diamante/ametista, nada de item.
# slots classico (777 e combos) + cara ou coroa.

import asyncio
import random
from math import comb

import discord
from discord import app_commands
from discord.ext import commands

import visual
import data

# ─── apostas ───

# faixas fixas: sem valor quebrado, sem all-in que quebra a economia.
VALORES = (10, 50, 100)

ALIAS_MOEDA = {
    "dima": "dima",
    "diamante": "dima",
    "diamantes": "dima",
    "amet": "amet",
    "ametista": "amet",
}


def _moeda_emoji(moeda: str) -> str:
    return visual.DIAMANTE if moeda == "dima" else visual.AMETHYST


def _parse_aposta(moeda_txt: str | None, valor_txt: str | None) -> tuple[str | None, int]:
    """prefixo livre -> (moeda, valor). (None, 0) se invalido.

    so o valor (`>slots 50`) vale dima.
    """
    txt_moeda = (moeda_txt or "").strip().lower()
    txt_valor = (valor_txt or "").strip()
    if txt_moeda.isdigit() and not txt_valor:
        txt_moeda, txt_valor = "dima", txt_moeda
    moeda = ALIAS_MOEDA.get(txt_moeda, "")
    try:
        valor = int(txt_valor or 0)
    except (TypeError, ValueError):
        valor = 0
    if not moeda or valor not in VALORES:
        return None, 0
    return moeda, valor


async def _cobrar(user_id: int, moeda: str, valor: int) -> bool:
    """tira a aposta. False se sem saldo."""
    if moeda == "dima":
        dima, _, _ = await asyncio.to_thread(data.buscar_saldo, user_id)
        if dima < valor:
            return False
        await asyncio.to_thread(data.adicionar_diamantes, user_id, -valor)
    else:
        _, amet, _ = await asyncio.to_thread(data.buscar_saldo, user_id)
        if amet < valor:
            return False
        await asyncio.to_thread(data.adicionar_ametista, user_id, -valor)
    return True


async def _sumir(msg, segundos: int = 15):
    """apaga a msg depois do prazo. derrota some, vitoria fica."""
    await asyncio.sleep(segundos)
    try:
        await msg.delete()
    except Exception:
        pass


async def _premiar(user_id: int, moeda: str, ganho: int, apostado: int) -> None:
    """paga o premio e registra a aposta pros stats do >player."""
    await asyncio.to_thread(data.registrar_aposta, user_id, ganho > apostado)
    if ganho <= 0:
        return
    if moeda == "dima":
        await asyncio.to_thread(data.adicionar_diamantes, user_id, ganho)
    else:
        await asyncio.to_thread(data.adicionar_ametista, user_id, ganho)


# ─── slots ───

SIMBOLOS = ["7️⃣", "💎", "⭐", "🔔", "🍒", "🍋"]
PESOS = [1, 2, 3, 4, 5, 5]

# trinca paga o multiplo; par devolve a aposta; resto perde.
PAGA_TRINCA = {"7️⃣": 10, "💎": 5, "⭐": 4, "🔔": 3, "🍒": 2, "🍋": 2}


def _girar() -> list[str]:
    return random.choices(SIMBOLOS, weights=PESOS, k=3)


def _premio_slots(itens: list[str], aposta: int) -> int:
    a, b, c = itens
    if a == b == c:
        return aposta * PAGA_TRINCA[a]
    if a == b or b == c or a == c:
        return aposta
    return 0


def _texto_premio(premio: int, aposta: int, moeda: str) -> tuple[str, int]:
    """(linha do resultado, cor)."""
    if premio > aposta:
        return (
            f"ganhou **{premio}** {_moeda_emoji(moeda)}!",
            visual.SUCCESS,
        )
    if premio == aposta:
        return ("devolveu a aposta. tenta de novo!", visual.WARNING)
    return ("perdeu. a banca agradece.", visual.ERROR)


def _embed_slots(titulo: str, r1: str, r2: str, r3: str, linha: str, cor: int) -> discord.Embed:
    embed = discord.Embed(
        title=titulo,
        description=f"# {r1} {r2} {r3}\n{linha}",
        color=cor,
    )
    embed.set_footer(text=visual.FOOTER)
    return embed


async def _animar_slots(edit, titulo: str, itens: list[str]) -> None:
    """revela os 3 rolos um por vez."""
    await edit(embed=_embed_slots(titulo, "❓", "❓", "❓", "girando...", visual.PRIMARY))
    await asyncio.sleep(0.7)
    await edit(embed=_embed_slots(titulo, itens[0], "❓", "❓", "girando...", visual.PRIMARY))
    await asyncio.sleep(0.7)
    await edit(
        embed=_embed_slots(titulo, itens[0], itens[1], "❓", "girando...", visual.PRIMARY)
    )
    await asyncio.sleep(0.7)


# ─── cara ou coroa ───

LADOS = ("cara", "coroa")


def _jogar_moeda(escolha: str) -> tuple[bool, str]:
    """(ganhou, lado que saiu)."""
    lado = random.choice(LADOS)
    return lado == escolha, lado


# ─── view ───


class BetView(discord.ui.View):
    """botao girar de novo com a mesma aposta. so quem abriu usa. expira em 2min."""

    def __init__(self, dono_id: int, jogo: str, moeda: str, valor: int, escolha: str = ""):
        super().__init__(timeout=120)
        self.dono_id = dono_id
        self.jogo = jogo
        self.moeda = moeda
        self.valor = valor
        self.escolha = escolha

    @discord.ui.button(label="de novo", emoji="🎰", style=discord.ButtonStyle.primary)
    async def denovo(self, interaction: discord.Interaction, _: discord.ui.Button):
        if interaction.user.id != self.dono_id:
            await interaction.response.send_message(
                "só quem apostou usa esse botão!", ephemeral=True
            )
            return
        if not await _cobrar(self.dono_id, self.moeda, self.valor):
            await interaction.response.send_message(
                f"sem saldo! a aposta é **{self.valor}** {_moeda_emoji(self.moeda)}.",
                ephemeral=True,
            )
            return
        if self.jogo == "coin":
            ganhou, lado = _jogar_moeda(self.escolha)
            premio = self.valor * 2 if ganhou else 0
            await _premiar(self.dono_id, self.moeda, premio, self.valor)
            linha = (
                f"saiu **{lado}** — ganhou **{premio}** {_moeda_emoji(self.moeda)}!"
                if ganhou
                else f"saiu **{lado}** — perdeu."
            )
            embed = discord.Embed(
                title="🪙 cara ou coroa",
                description=f"você escolheu **{self.escolha}**.\n{linha}",
                color=visual.SUCCESS if ganhou else visual.ERROR,
            )
            embed.set_footer(text=visual.FOOTER)
            await interaction.response.send_message(embed=embed, view=self)
            return
        itens = _girar()
        premio = _premio_slots(itens, self.valor)
        await _premiar(self.dono_id, self.moeda, premio, self.valor)
        linha, cor = _texto_premio(premio, self.valor, self.moeda)
        titulo = "🎰 slots"
        await interaction.response.send_message(
            embed=_embed_slots(titulo, "❓", "❓", "❓", "girando...", visual.PRIMARY)
        )
        await asyncio.sleep(0.7)
        await interaction.edit_original_response(
            embed=_embed_slots(titulo, itens[0], "❓", "❓", "girando...", visual.PRIMARY)
        )
        await asyncio.sleep(0.7)
        await interaction.edit_original_response(
            embed=_embed_slots(
                titulo, itens[0], itens[1], "❓", "girando...", visual.PRIMARY
            )
        )
        await asyncio.sleep(0.7)
        await interaction.edit_original_response(
            embed=_embed_slots(titulo, *itens, linha, cor), view=self
        )
        # derrota some em 15s, vitoria fica no chat.
        if premio <= self.valor:
            asyncio.create_task(_sumir(await interaction.original_response()))


def _embed_bet(barra: str) -> discord.Embed:
    """hub do axolotl bet: jogos + combos + faixas."""
    embed = discord.Embed(
        title="🎰 axolotl bet",
        description="o cassino do lago. só moeda: ganha ou perde diamante/ametista, nada de item.",
        color=visual.PRIMARY,
    )
    embed.add_field(
        name="🎰 slots",
        value=(
            f"`{barra}slots <dima|amet> <10|50|100>`\n"
            + "\n".join(f"{s} {s} {s} — **{m}x**" for s, m in PAGA_TRINCA.items())
            + "\npar devolve a aposta."
        ),
        inline=False,
    )
    embed.add_field(
        name="🪙 cara ou coroa",
        value=(
            f"`{barra}caraoucoroa <cara|coroa> <dima|amet> <10|50|100>`\n"
            "50/50, paga **2x**."
        ),
        inline=False,
    )
    embed.add_field(
        name="⛏️ mines",
        value=(
            f"`{barra}mines <dima|amet> <10|50|100> [minas 1-8]`\n"
            "20 pedras, N bombas. cada 💎 aumenta o multi, 💣 perde tudo. retire quando quiser."
        ),
        inline=False,
    )
    embed.set_footer(text=f"faixas 10/50/100 • derrota some, vitória fica • {visual.FOOTER}")
    return embed


# ─── mines ───

MINAS_TOTAL = 20  # 4 fileiras x 5 + fileira do retirar
MINAS_MIN, MINAS_MAX, MINAS_PADRAO = 1, 8, 3

# dono_id -> {moeda, valor, minas:set, abertos:set, view}.
# 1 jogo por pessoa: comecar outro reembolsa o anterior.
JOGOS_MINES: dict[int, dict] = {}


def _mult_mines(abertos: int, minas: int) -> float:
    """multiplicador justo com ~3% pra banca."""
    if abertos <= 0:
        return 1.0
    return comb(MINAS_TOTAL, minas) / comb(MINAS_TOTAL - abertos, minas) * 0.97


def _embed_mines(jogo: dict, fim: str = "") -> discord.Embed:
    """placar do jogo: multi atual + potencial."""
    mult = _mult_mines(len(jogo["abertos"]), len(jogo["minas"]))
    potencial = int(jogo["valor"] * mult)
    desc = (
        f"💣 **{len(jogo['minas'])}** bombas em **{MINAS_TOTAL}** pedras\n"
        f"multi **{mult:.2f}x** · potencial **{potencial}** {_moeda_emoji(jogo['moeda'])}"
    )
    if fim:
        desc += f"\n{fim}"
    embed = discord.Embed(
        title="⛏️ mines",
        description=desc,
        color=visual.PRIMARY,
    )
    embed.set_footer(text="retire quando quiser • 5min sem jogar encerra • " + visual.FOOTER)
    return embed


def _pintar_mines(view: discord.ui.View, jogo: dict, revelar_tudo: bool = False) -> None:
    """atualiza os botoes: 💎 aberto, 💣 bomba, ⬜ fechado."""
    for b in view.children:
        cid = b.custom_id or ""
        if cid == "mines:sacar":
            b.disabled = revelar_tudo
            continue
        idx = int(cid.split(":")[1])
        if idx in jogo["abertos"]:
            bomba = idx in jogo["minas"]
            b.label = "💣" if bomba else "💎"
            b.style = (
                discord.ButtonStyle.danger if bomba else discord.ButtonStyle.success
            )
            b.disabled = True
        elif revelar_tudo:
            b.label = "💣" if idx in jogo["minas"] else "💎"
            b.disabled = True


async def _comecar_mines(user_id: int, moeda: str, valor: int, minas: int):
    """cobra (reembolsando jogo antigo) e cria o jogo. None se sem saldo."""
    velho = JOGOS_MINES.pop(user_id, None)
    if velho is not None:
        # reembolso nao e aposta: devolve sem registrar.
        if velho["moeda"] == "dima":
            await asyncio.to_thread(data.adicionar_diamantes, user_id, velho["valor"])
        else:
            await asyncio.to_thread(data.adicionar_ametista, user_id, velho["valor"])
    if not await _cobrar(user_id, moeda, valor):
        return None
    view = MinesView(user_id)
    JOGOS_MINES[user_id] = {
        "moeda": moeda,
        "valor": valor,
        "minas": set(random.sample(range(MINAS_TOTAL), minas)),
        "abertos": set(),
        "view": view,
    }
    return view


async def _cavar(interaction: discord.Interaction, dono_id: int, idx: int):
    jogo = JOGOS_MINES.get(dono_id)
    if jogo is None:
        await interaction.response.send_message(
            "esse jogo expirou! abre outro com `>mines`.", ephemeral=True
        )
        return
    if interaction.user.id != dono_id:
        await interaction.response.send_message(
            "esse jogo não é seu!", ephemeral=True
        )
        return
    if idx in jogo["abertos"]:
        await interaction.response.send_message("essa pedra já foi!", ephemeral=True)
        return
    jogo["abertos"].add(idx)
    view = jogo["view"]
    if idx in jogo["minas"]:
        # bomba: perde tudo, some em 15s.
        await asyncio.to_thread(data.registrar_aposta, dono_id, False)
        JOGOS_MINES.pop(dono_id, None)
        _pintar_mines(view, jogo, revelar_tudo=True)
        await interaction.response.edit_message(
            embed=_embed_mines(jogo, fim=f"💣 **bum!** perdeu **{jogo['valor']}** {_moeda_emoji(jogo['moeda'])}."),
            view=view,
        )
        asyncio.create_task(_sumir(await interaction.original_response()))
        return
    if len(jogo["abertos"]) == MINAS_TOTAL - len(jogo["minas"]):
        # limpou tudo: saca sozinho.
        await _sacar_jogo(dono_id, interaction, auto=True)
        return
    _pintar_mines(view, jogo)
    await interaction.response.edit_message(embed=_embed_mines(jogo), view=view)


async def _sacar_jogo(dono_id: int, interaction: discord.Interaction, auto: bool = False):
    """retira com o multi atual. vitoria fica, resto some em 15s."""
    jogo = JOGOS_MINES.pop(dono_id, None)
    if jogo is None:
        await interaction.response.send_message(
            "esse jogo expirou! abre outro com `>mines`.", ephemeral=True
        )
        return
    mult = _mult_mines(len(jogo["abertos"]), len(jogo["minas"]))
    premio = int(jogo["valor"] * mult)
    await _premiar(dono_id, jogo["moeda"], premio, jogo["valor"])
    _pintar_mines(jogo["view"], jogo, revelar_tudo=True)
    fim = (
        f"🧹 **limpou tudo!** sacou **{premio}** {_moeda_emoji(jogo['moeda'])} (**{mult:.2f}x**)."
        if auto
        else f"💰 sacou **{premio}** {_moeda_emoji(jogo['moeda'])} (**{mult:.2f}x**)."
    )
    await interaction.response.edit_message(
        embed=_embed_mines(jogo, fim=fim), view=jogo["view"]
    )
    if premio <= jogo["valor"]:
        asyncio.create_task(_sumir(await interaction.original_response()))


class MinesView(discord.ui.View):
    """grid 20 pedras + retirar. so o dono clica. expira em 5min."""

    def __init__(self, dono_id: int):
        super().__init__(timeout=300)
        self.dono_id = dono_id
        for i in range(MINAS_TOTAL):
            b = discord.ui.Button(
                label="⬜",
                style=discord.ButtonStyle.secondary,
                custom_id=f"mines:{i}",
                row=i // 5,
            )
            b.callback = self._fabrica(i)
            self.add_item(b)
        sacar = discord.ui.Button(
            label="retirar",
            emoji="💰",
            style=discord.ButtonStyle.success,
            custom_id="mines:sacar",
            row=4,
        )
        sacar.callback = self._sacar
        self.add_item(sacar)

    def _fabrica(self, idx: int):
        async def cavar(interaction: discord.Interaction):
            await _cavar(interaction, self.dono_id, idx)

        return cavar

    async def _sacar(self, interaction: discord.Interaction):
        if interaction.user.id != self.dono_id:
            await interaction.response.send_message(
                "esse jogo não é seu!", ephemeral=True
            )
            return
        await _sacar_jogo(self.dono_id, interaction)

    async def on_timeout(self):
        JOGOS_MINES.pop(self.dono_id, None)


class Bet(commands.Cog, name="Axolotl Bet"):
    """cassino: slots, cara ou coroa e mines valendo moeda."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ─── >bet ───
    @commands.command(name="bet")
    async def bet(self, ctx: commands.Context):
        """o hub do axolotl bet."""
        await ctx.send(embed=_embed_bet(">"))

    @app_commands.command(name="bet", description="o hub do axolotl bet.")
    async def bet_slash(self, interaction: discord.Interaction):
        """versão slash do >bet."""
        await interaction.response.send_message(embed=_embed_bet("/"))

    # ─── >slots ───
    @commands.command(name="slots")
    async def slots(self, ctx: commands.Context, moeda_txt: str = "", valor_txt: str = ""):
        """slots: `>slots dima 50` (ou `>slots 50` que vale dima). trinca paga até 10x."""
        moeda, valor = _parse_aposta(moeda_txt, valor_txt)
        if moeda is None:
            await ctx.send(
                "🎰 uso: `>slots <dima|amet> <10|50|100>`. ex: `>slots 50`."
            )
            return
        if not await _cobrar(ctx.author.id, moeda, valor):
            dima, amet, _ = await asyncio.to_thread(data.buscar_saldo, ctx.author.id)
            saldo = dima if moeda == "dima" else amet
            await ctx.send(
                f"🎰 a aposta é **{valor}** {_moeda_emoji(moeda)}! (você tem **{saldo}**)"
            )
            return
        itens = _girar()
        premio = _premio_slots(itens, valor)
        await _premiar(ctx.author.id, moeda, premio, valor)
        linha, cor = _texto_premio(premio, valor, moeda)
        titulo = "🎰 slots"
        msg = await ctx.send(
            embed=_embed_slots(titulo, "❓", "❓", "❓", "girando...", visual.PRIMARY)
        )
        await asyncio.sleep(0.7)
        await msg.edit(embed=_embed_slots(titulo, itens[0], "❓", "❓", "girando...", visual.PRIMARY))
        await asyncio.sleep(0.7)
        await msg.edit(
            embed=_embed_slots(titulo, itens[0], itens[1], "❓", "girando...", visual.PRIMARY)
        )
        await asyncio.sleep(0.7)
        await msg.edit(
            embed=_embed_slots(titulo, *itens, linha, cor),
            view=BetView(ctx.author.id, "slots", moeda, valor),
        )
        # derrota some em 15s, vitoria fica no chat.
        if premio <= valor:
            asyncio.create_task(_sumir(msg))

    @app_commands.command(name="slots", description="slots: trinca paga até 10x.")
    @app_commands.describe(moeda="qual moeda apostar", valor="quanto apostar")
    @app_commands.choices(
        moeda=[
            app_commands.Choice(name="diamantes", value="dima"),
            app_commands.Choice(name="ametista", value="amet"),
        ],
        valor=[
            app_commands.Choice(name="10", value=10),
            app_commands.Choice(name="50", value=50),
            app_commands.Choice(name="100", value=100),
        ],
    )
    async def slots_slash(self, interaction: discord.Interaction, moeda: str, valor: int):
        """versão slash do >slots."""
        if not await _cobrar(interaction.user.id, moeda, valor):
            await interaction.response.send_message(
                f"🎰 a aposta é **{valor}** {_moeda_emoji(moeda)}!",
                ephemeral=True,
            )
            return
        itens = _girar()
        premio = _premio_slots(itens, valor)
        await _premiar(interaction.user.id, moeda, premio, valor)
        linha, cor = _texto_premio(premio, valor, moeda)
        titulo = "🎰 slots"
        await interaction.response.send_message(
            embed=_embed_slots(titulo, "❓", "❓", "❓", "girando...", visual.PRIMARY)
        )
        await _animar_slots(interaction.edit_original_response, titulo, itens)
        await interaction.edit_original_response(
            embed=_embed_slots(titulo, *itens, linha, cor),
            view=BetView(interaction.user.id, "slots", moeda, valor),
        )
        # derrota some em 15s, vitoria fica no chat.
        if premio <= valor:
            asyncio.create_task(_sumir(await interaction.original_response()))

    # ─── >caraoucoroa ───
    @commands.command(name="caraoucoroa")
    async def caraoucoroa(
        self, ctx: commands.Context, escolha: str = "", moeda_txt: str = "", valor_txt: str = ""
    ):
        """50/50: `>caraoucoroa coroa dima 10`. paga 2x."""
        escolha = escolha.lower()
        moeda, valor = _parse_aposta(moeda_txt, valor_txt)
        if escolha not in LADOS or moeda is None:
            await ctx.send(
                "🪙 uso: `>caraoucoroa <cara|coroa> <dima|amet> <10|50|100>`."
            )
            return
        if not await _cobrar(ctx.author.id, moeda, valor):
            await ctx.send(f"🪙 a aposta é **{valor}** {_moeda_emoji(moeda)}!")
            return
        ganhou, lado = _jogar_moeda(escolha)
        premio = valor * 2 if ganhou else 0
        await _premiar(ctx.author.id, moeda, premio, valor)
        linha = (
            f"saiu **{lado}** — ganhou **{premio}** {_moeda_emoji(moeda)}!"
            if ganhou
            else f"saiu **{lado}** — perdeu."
        )
        embed = discord.Embed(
            title="🪙 cara ou coroa",
            description=f"{ctx.author.mention} escolheu **{escolha}**.\n{linha}",
            color=visual.SUCCESS if ganhou else visual.ERROR,
        )
        embed.set_footer(text=visual.FOOTER)
        await ctx.send(
            embed=embed, view=BetView(ctx.author.id, "coin", moeda, valor, escolha)
        )

    @app_commands.command(name="caraoucoroa", description="50/50 valendo moeda. paga 2x.")
    @app_commands.describe(
        escolha="cara ou coroa", moeda="qual moeda apostar", valor="quanto apostar"
    )
    @app_commands.choices(
        escolha=[
            app_commands.Choice(name="cara", value="cara"),
            app_commands.Choice(name="coroa", value="coroa"),
        ],
        moeda=[
            app_commands.Choice(name="diamantes", value="dima"),
            app_commands.Choice(name="ametista", value="amet"),
        ],
        valor=[
            app_commands.Choice(name="10", value=10),
            app_commands.Choice(name="50", value=50),
            app_commands.Choice(name="100", value=100),
        ],
    )
    async def caraoucoroa_slash(
        self, interaction: discord.Interaction, escolha: str, moeda: str, valor: int
    ):
        """versão slash do >caraoucoroa."""
        if not await _cobrar(interaction.user.id, moeda, valor):
            await interaction.response.send_message(
                f"🪙 a aposta é **{valor}** {_moeda_emoji(moeda)}!",
                ephemeral=True,
            )
            return
        ganhou, lado = _jogar_moeda(escolha)
        premio = valor * 2 if ganhou else 0
        await _premiar(interaction.user.id, moeda, premio, valor)
        linha = (
            f"saiu **{lado}** — ganhou **{premio}** {_moeda_emoji(moeda)}!"
            if ganhou
            else f"saiu **{lado}** — perdeu."
        )
        embed = discord.Embed(
            title="🪙 cara ou coroa",
            description=f"você escolheu **{escolha}**.\n{linha}",
            color=visual.SUCCESS if ganhou else visual.ERROR,
        )
        embed.set_footer(text=visual.FOOTER)
        await interaction.response.send_message(
            embed=embed,
            view=BetView(interaction.user.id, "coin", moeda, valor, escolha),
        )

    # ─── >mines ───
    @commands.command(name="mines")
    async def mines(
        self, ctx: commands.Context, moeda_txt: str = "", valor_txt: str = "", minas_txt: str = ""
    ):
        """mines: `>mines dima 50 3`. ache 💎, fuja da 💣, retire quando quiser."""
        moeda, valor = _parse_aposta(moeda_txt, valor_txt)
        try:
            minas = int(minas_txt or MINAS_PADRAO)
        except (TypeError, ValueError):
            minas = 0
        if moeda is None or not MINAS_MIN <= minas <= MINAS_MAX:
            await ctx.send(
                f"⛏️ uso: `>mines <dima|amet> <10|50|100> [minas {MINAS_MIN}-{MINAS_MAX}]`. "
                "ex: `>mines 50 3`."
            )
            return
        tinha = ctx.author.id in JOGOS_MINES
        view = await _comecar_mines(ctx.author.id, moeda, valor, minas)
        if view is None:
            await ctx.send(f"⛏️ precisa de **{valor}** {_moeda_emoji(moeda)} pra entrar!")
            return
        msg = f"{ctx.author.mention} reembolsei o jogo anterior. " if tinha else ""
        await ctx.send(
            content=msg or None,
            embed=_embed_mines(JOGOS_MINES[ctx.author.id]),
            view=view,
        )

    @app_commands.command(name="mines", description="mines: ache 💎, fuja da 💣, retire quando quiser.")
    @app_commands.describe(
        moeda="qual moeda apostar",
        valor="quanto apostar",
        minas="quantas bombas (1-8)",
    )
    @app_commands.choices(
        moeda=[
            app_commands.Choice(name="diamantes", value="dima"),
            app_commands.Choice(name="ametista", value="amet"),
        ],
        valor=[
            app_commands.Choice(name="10", value=10),
            app_commands.Choice(name="50", value=50),
            app_commands.Choice(name="100", value=100),
        ],
    )
    async def mines_slash(
        self,
        interaction: discord.Interaction,
        moeda: str,
        valor: int,
        minas: app_commands.Range[int, 1, 8] = 3,
    ):
        """versão slash do >mines."""
        tinha = interaction.user.id in JOGOS_MINES
        view = await _comecar_mines(interaction.user.id, moeda, valor, minas)
        if view is None:
            await interaction.response.send_message(
                f"⛏️ precisa de **{valor}** {_moeda_emoji(moeda)} pra entrar!",
                ephemeral=True,
            )
            return
        msg = "reembolsei o jogo anterior. " if tinha else ""
        await interaction.response.send_message(
            content=msg or None,
            embed=_embed_mines(JOGOS_MINES[interaction.user.id]),
            view=view,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Bet(bot))
