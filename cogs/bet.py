# isso aq e o axolotl bet: cassino so com moeda.
# ganha ou perde so diamante/ametista, nada de item.
# slots classico (777 e combos) + cara ou coroa.

import asyncio
import logging
import random
from math import comb

import discord
from discord import app_commands
from discord.ext import commands

import visual
import data

log = logging.getLogger("alt.bet")

# ─── apostas ───

# vale qualquer valor de 1 a 1000. teto anti all-in que quebra a economia.
MIN_APOSTA, MAX_APOSTA = 1, 1000

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
    if not moeda or not MIN_APOSTA <= valor <= MAX_APOSTA:
        return None, 0
    return moeda, valor


async def _cobrar(user_id: int, moeda: str, valor: int) -> tuple[bool, int]:
    """tira a aposta numa transacao so. retorna (ok, saldo_atual)."""
    return await asyncio.to_thread(data.debitar_moeda, user_id, moeda, valor)


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
        ok, _saldo = await _cobrar(self.dono_id, self.moeda, self.valor)
        if not ok:
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
        await _animar_slots(interaction.edit_original_response, titulo, itens)
        await interaction.edit_original_response(
            embed=_embed_slots(titulo, *itens, linha, cor), view=self
        )
        # derrota some em 15s, vitoria fica no chat.
        if premio <= self.valor:
            asyncio.create_task(_sumir(await interaction.original_response()))


def _embed_bet(barra: str) -> discord.Embed:
    """hub do axolotl bet: jogos + combos + valores."""
    embed = discord.Embed(
        title="🎰 axolotl bet",
        description="o cassino do lago. só moeda: ganha ou perde diamante/ametista, nada de item.",
        color=visual.PRIMARY,
    )
    embed.add_field(
        name="🎰 slots",
        value=(
            f"`{barra}slots <dima|amet> <1-1000>`\n"
            + "\n".join(f"{s} {s} {s} — **{m}x**" for s, m in PAGA_TRINCA.items())
            + "\npar devolve a aposta."
        ),
        inline=False,
    )
    embed.add_field(
        name="🪙 cara ou coroa",
        value=(
            f"`{barra}caraoucoroa <cara|coroa> <dima|amet> <1-1000>`\n"
            "50/50, paga **2x**."
        ),
        inline=False,
    )
    embed.add_field(
        name="⛏️ mines",
        value=(
            f"`{barra}mines <dima|amet> <1-1000>`\n"
            "20 pedras. quanto maior a aposta, mais bombas (3 a 15) e maior o multi. "
            "min 3 abertas pra retirar, 💣 perde tudo. max 10x / 5k."
        ),
        inline=False,
    )
    embed.set_footer(text=f"vale 1-1000 • derrota some, vitória fica • {visual.FOOTER}")
    return embed


# ─── mines ───

MINAS_TOTAL = 20  # 5x4 + retirar (limite do discord: 25 por msg).
MINAS_MINIMO_SAQUE = 3  # pedras abertas pra poder retirar

# quanto maior a aposta, mais mina (e mais multi).
FAIXAS_MINA = ((600, 15), (300, 12), (150, 8), (50, 5), (1, 3))


def _minas_por_valor(valor: int) -> int:
    """faixa da aposta -> n de minas."""
    for piso, minas in FAIXAS_MINA:
        if valor >= piso:
            return minas
    return 3

JOGO_EXPIRADO = "jogo acabou! restart devolve a aposta."


# 1 trava por pessoa: duplo clique no mesmo jogo processa em fila, nunca junto.
_TRAVAS_MINES: dict[int, asyncio.Lock] = {}


def _trava_mines(user_id: int) -> asyncio.Lock:
    trava = _TRAVAS_MINES.get(user_id)
    if trava is None:
        trava = asyncio.Lock()
        _TRAVAS_MINES[user_id] = trava
    return trava


async def _reembolsar(user_id: int, jogo: dict) -> None:
    """devolve a aposta sem registrar (reembolso nao e aposta)."""
    if jogo["moeda"] == "dima":
        await asyncio.to_thread(data.adicionar_diamantes, user_id, jogo["valor"])
    else:
        await asyncio.to_thread(data.adicionar_ametista, user_id, jogo["valor"])


# teto do mines: sem cap um hit paga 100k x e quebra a economia.
MULT_MAX = 10.0
PREMIO_MAX = 5000


def _mult_mines(abertos: int, minas: int) -> float:
    """multiplicador com ~20% pra banca, teto 10x (igual o slots)."""
    if abertos <= 0:
        return 1.0
    if MINAS_TOTAL - abertos < minas:
        return MULT_MAX
    mult = comb(MINAS_TOTAL, minas) / comb(MINAS_TOTAL - abertos, minas) * 0.80
    return min(mult, MULT_MAX)


def _premio_mines(valor: int, abertos: int, minas: int) -> int:
    """premio com teto 5k: trava a variancia sem matar a graça."""
    return min(int(valor * _mult_mines(abertos, minas)), PREMIO_MAX)


def _embed_mines(jogo: dict, fim: str = "") -> discord.Embed:
    """placar do jogo numa linha: bombas, multi e potencial."""
    mult = _mult_mines(len(jogo["abertos"]), len(jogo["minas"]))
    potencial = int(jogo["valor"] * mult)
    desc = f"💣 {len(jogo['minas'])} · **{mult:.2f}x** · potencial **{potencial}** {_moeda_emoji(jogo['moeda'])}"
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


async def _comecar_mines(user_id: int, moeda: str, valor: int):
    """cobra (reembolsando jogo antigo) e salva no banco. None se sem saldo."""
    async with _trava_mines(user_id):
        return await _comecar_mines_nucleo(user_id, moeda, valor)


async def _comecar_mines_nucleo(user_id: int, moeda: str, valor: int):
    """corpo do _comecar_mines (trava ja segurada). minas pela aposta."""
    velho = await asyncio.to_thread(data.remover_mines, user_id)
    if velho is not None:
        await _reembolsar(user_id, velho)
    ok, _saldo = await _cobrar(user_id, moeda, valor)
    if not ok:
        return None
    minas = _minas_por_valor(valor)
    await asyncio.to_thread(
        data.salvar_mines, user_id, moeda, valor, set(random.sample(range(MINAS_TOTAL), minas))
    )
    return MinesView(user_id)


async def _cavar(interaction: discord.Interaction, dono_id: int, idx: int):
    # dono eh checagem gratis: nega na hora, sem defer.
    if interaction.user.id != dono_id:
        await interaction.response.send_message(
            "esse jogo não é seu!", ephemeral=True
        )
        return
    # defer primeiro: confirma em ms e ganha 15min. sem isso, pico de
    # gente estoura os 3s e o clique "falha" mesmo funcionando.
    try:
        await interaction.response.defer()
    except Exception:
        return
    async with _trava_mines(dono_id):
        await _cavar_nucleo(interaction, dono_id, idx)


async def _cavar_nucleo(interaction: discord.Interaction, dono_id: int, idx: int):
    """corpo do _cavar (ja com defer, trava segurada). 1 ida ao banco."""
    edit = interaction.edit_original_response

    async def erro(texto: str):
        try:
            await interaction.followup.send(texto, ephemeral=True)
        except Exception:
            pass

    res = await asyncio.to_thread(data.abrir_mines, dono_id, idx)
    if res[0] is None:
        log.info(
            "mines: clique sem jogo (dono=%d, user=%d, tile=%d)",
            dono_id,
            interaction.user.id,
            idx,
        )
        await erro(JOGO_EXPIRADO)
        return
    jogo, nova = res
    if not nova:
        # 💎 aberto = retirar.
        await _sacar_nucleo(dono_id, interaction)
        return
    view = MinesView(dono_id)
    if idx in jogo["minas"]:
        # bomba: mostra tudo e depois some so os botoes, o embed fica.
        await asyncio.to_thread(data.registrar_aposta, dono_id, False)
        await asyncio.to_thread(data.remover_mines, dono_id)
        fim = f"💣 **bum!** perdeu **{jogo['valor']}** {_moeda_emoji(jogo['moeda'])}."
        _pintar_mines(view, jogo, revelar_tudo=True)
        await edit(embed=_embed_mines(jogo, fim=fim), view=view)
        await asyncio.sleep(5)
        try:
            await edit(embed=_embed_mines(jogo, fim=fim), view=None)
        except Exception:
            pass
        return
    if len(jogo["abertos"]) == MINAS_TOTAL - len(jogo["minas"]):
        # limpou tudo: saca sozinho (nucleo: a trava ja esta segurada).
        await _sacar_nucleo(dono_id, interaction, auto=True)
        return
    _pintar_mines(view, jogo)
    try:
        await edit(embed=_embed_mines(jogo), view=view)
    except Exception:
        pass


async def _sacar_nucleo(dono_id: int, interaction: discord.Interaction, auto: bool = False):
    """retira com o multi atual. botoes saem, embed fica. (ja com defer)."""
    edit = interaction.edit_original_response
    if not auto:
        jogo = await asyncio.to_thread(data.buscar_mines, dono_id)
        if jogo is None:
            log.info(
                "mines: saque sem jogo (dono=%d, user=%d)",
                dono_id,
                interaction.user.id,
            )
            try:
                await interaction.followup.send(JOGO_EXPIRADO, ephemeral=True)
            except Exception:
                pass
            return
        if len(jogo["abertos"]) < MINAS_MINIMO_SAQUE:
            try:
                await interaction.followup.send(
                    f"abre ao menos **{MINAS_MINIMO_SAQUE}** pedras pra retirar!",
                    ephemeral=True,
                )
            except Exception:
                pass
            return
    jogo = await asyncio.to_thread(data.remover_mines, dono_id)
    if jogo is None:
        try:
            await interaction.followup.send(JOGO_EXPIRADO, ephemeral=True)
        except Exception:
            pass
        return
    mult = _mult_mines(len(jogo["abertos"]), len(jogo["minas"]))
    premio = _premio_mines(jogo["valor"], len(jogo["abertos"]), len(jogo["minas"]))
    await _premiar(dono_id, jogo["moeda"], premio, jogo["valor"])
    fim = (
        f"🧹 **limpou tudo!** sacou **{premio}** {_moeda_emoji(jogo['moeda'])} (**{mult:.2f}x**)."
        if auto
        else f"💰 sacou **{premio}** {_moeda_emoji(jogo['moeda'])} (**{mult:.2f}x**)."
    )
    try:
        await edit(embed=_embed_mines(jogo, fim=fim), view=None)
    except Exception:
        pass


class MinesView(discord.ui.View):
    """grid 20 pedras + retirar. so o dono clica. expira em 5min."""

    def __init__(self, dono_id: int):
        super().__init__(timeout=300)
        self.dono_id = dono_id
        # msg com os botoes (anexada por quem cria): no timeout os botoes somem.
        self.message = None
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
        try:
            await interaction.response.defer()
        except Exception:
            return
        async with _trava_mines(self.dono_id):
            await _sacar_nucleo(self.dono_id, interaction)

    async def on_timeout(self):
        # 5min parado: devolve a aposta e tira os botoes (sem botao, sem erro).
        jogo = await asyncio.to_thread(data.remover_mines, self.dono_id)
        if jogo is not None:
            await _reembolsar(self.dono_id, jogo)
            log.info("mines: reembolso por timeout pra %d", self.dono_id)
        if self.message is not None:
            try:
                await self.message.edit(view=None)
            except Exception:
                pass


class Bet(commands.Cog, name="Axolotl Bet"):
    """cassino: slots, cara ou coroa e mines valendo moeda."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        # restart no meio do jogo: devolve as apostas presas.
        try:
            pendentes = await asyncio.to_thread(data.listar_mines)
        except Exception:
            log.exception("mines: falha ao listar pendentes no boot")
            return
        for jogo in pendentes:
            try:
                await _reembolsar(jogo["user_id"], jogo)
                await asyncio.to_thread(data.remover_mines, jogo["user_id"])
            except Exception:
                log.exception("mines: falha ao reembolsar %d", jogo["user_id"])
        if pendentes:
            log.info("mines: %d aposta(s) reembolsada(s) pos-restart", len(pendentes))

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
                "🎰 uso: `>slots <dima|amet> <1-1000>`. ex: `>slots 67`."
            )
            return
        ok, saldo = await _cobrar(ctx.author.id, moeda, valor)
        if not ok:
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
    @app_commands.describe(moeda="qual moeda apostar", valor="quanto apostar (1-1000)")
    @app_commands.choices(
        moeda=[
            app_commands.Choice(name="diamantes", value="dima"),
            app_commands.Choice(name="ametista", value="amet"),
        ]
    )
    async def slots_slash(
        self, interaction: discord.Interaction, moeda: str, valor: app_commands.Range[int, 1, 1000]
    ):
        """versão slash do >slots."""
        ok, _saldo = await _cobrar(interaction.user.id, moeda, valor)
        if not ok:
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
                "🪙 uso: `>caraoucoroa <cara|coroa> <dima|amet> <1-1000>`."
            )
            return
        ok, _saldo = await _cobrar(ctx.author.id, moeda, valor)
        if not ok:
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
        escolha="cara ou coroa", moeda="qual moeda apostar", valor="quanto apostar (1-1000)"
    )
    @app_commands.choices(
        escolha=[
            app_commands.Choice(name="cara", value="cara"),
            app_commands.Choice(name="coroa", value="coroa"),
        ],
        moeda=[
            app_commands.Choice(name="diamantes", value="dima"),
            app_commands.Choice(name="ametista", value="amet"),
        ]
    )
    async def caraoucoroa_slash(
        self,
        interaction: discord.Interaction,
        escolha: str,
        moeda: str,
        valor: app_commands.Range[int, 1, 1000],
    ):
        """versão slash do >caraoucoroa."""
        ok, _saldo = await _cobrar(interaction.user.id, moeda, valor)
        if not ok:
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
        self, ctx: commands.Context, moeda_txt: str = "", valor_txt: str = ""
    ):
        """mines: `>mines 50`. quanto maior a aposta, mais mina. min 3 pra sacar."""
        moeda, valor = _parse_aposta(moeda_txt, valor_txt)
        if moeda is None:
            await ctx.send(
                "⛏️ uso: `>mines <dima|amet> <1-1000>`. ex: `>mines 50`."
            )
            return
        tinha = await asyncio.to_thread(data.buscar_mines, ctx.author.id)
        view = await _comecar_mines(ctx.author.id, moeda, valor)
        if view is None:
            await ctx.send(f"⛏️ precisa de **{valor}** {_moeda_emoji(moeda)} pra entrar!")
            return
        jogo = await asyncio.to_thread(data.buscar_mines, ctx.author.id)
        msg = f"{ctx.author.mention} reembolsei o jogo anterior. " if tinha else ""
        enviada = await ctx.send(
            content=msg or None,
            embed=_embed_mines(jogo),
            view=view,
        )
        view.message = enviada

    @app_commands.command(name="mines", description="mines: ache 💎, fuja da 💣, retire quando quiser.")
    @app_commands.describe(
        moeda="qual moeda apostar",
        valor="quanto apostar (1-1000, mais = mais minas)",
    )
    @app_commands.choices(
        moeda=[
            app_commands.Choice(name="diamantes", value="dima"),
            app_commands.Choice(name="ametista", value="amet"),
        ]
    )
    async def mines_slash(
        self,
        interaction: discord.Interaction,
        moeda: str,
        valor: app_commands.Range[int, 1, 1000],
    ):
        """versão slash do >mines."""
        tinha = await asyncio.to_thread(data.buscar_mines, interaction.user.id)
        view = await _comecar_mines(interaction.user.id, moeda, valor)
        if view is None:
            await interaction.response.send_message(
                f"⛏️ precisa de **{valor}** {_moeda_emoji(moeda)} pra entrar!",
                ephemeral=True,
            )
            return
        jogo = await asyncio.to_thread(data.buscar_mines, interaction.user.id)
        msg = "reembolsei o jogo anterior. " if tinha else ""
        await interaction.response.send_message(
            content=msg or None,
            embed=_embed_mines(jogo),
            view=view,
        )
        try:
            view.message = await interaction.original_response()
        except Exception:
            pass


async def setup(bot: commands.Bot):
    await bot.add_cog(Bet(bot))
