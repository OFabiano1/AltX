# isso aq e o axolotl bet: cassino so com moeda.
# ganha ou perde so diamante/ametista, nada de item.
# slots classico (777 e combos) + cara ou coroa.

import asyncio
import random

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
    """prefixo livre -> (moeda, valor). (None, 0) se invalido."""
    moeda = ALIAS_MOEDA.get((moeda_txt or "").lower(), "")
    try:
        valor = int(valor_txt or 0)
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


async def _premiar(user_id: int, moeda: str, ganho: int) -> None:
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
            await _premiar(self.dono_id, self.moeda, premio)
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
        await _premiar(self.dono_id, self.moeda, premio)
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
    embed.set_footer(text=f"faixas 10/50/100 • {visual.FOOTER}")
    return embed


class Bet(commands.Cog, name="Axolotl Bet"):
    """cassino: slots e cara ou coroa valendo moeda."""

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
        """slots: `>slots dima 50`. trinca paga até 10x."""
        moeda, valor = _parse_aposta(moeda_txt, valor_txt)
        if moeda is None:
            await ctx.send(
                f"🎰 uso: `>slots <dima|amet> <10|50|100>`. ex: `>slots dima 50`."
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
        await _premiar(ctx.author.id, moeda, premio)
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
        await _premiar(interaction.user.id, moeda, premio)
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
        await _premiar(ctx.author.id, moeda, premio)
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
        await _premiar(interaction.user.id, moeda, premio)
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


async def setup(bot: commands.Bot):
    await bot.add_cog(Bet(bot))
