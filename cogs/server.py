# isso aq e o hub do servidor: comunidade, discord, site e projetos.
# so dado real: o do discord vem do guild, o resto e fato do dono.
# axolotl smp entra como projeto, ip so quando existir (sem numero inventado).

import asyncio
import datetime

import discord
from discord import app_commands
from discord.ext import commands

import data
import deadlock_api
import visual

# site da comunidade (fato do dono, mesmo do status).
SITE_URL = "https://axolotlbr.xyz"

# projetos do ecossistema. ip do smp so entra aqui quando existir.
PROJETOS = (
    ("Axolotl SMP", "servidor de minecraft da comunidade — ip em breve"),
    ("ALT", "o bot do discord — `>ajuda` pra ver tudo"),
    ("site", "axolotlbr.xyz"),
)


def _desde_2020(guild: discord.Guild | None) -> str:
    # idade real do servidor no discord, ou o marco da marca.
    if guild is not None and guild.created_at is not None:
        criacao = guild.created_at
        anos = max(0, datetime.datetime.now(datetime.timezone.utc).year - criacao.year)
        return f"no discord desde {criacao.year} ({anos} anos)"
    return "desde 2020"


def _embed_hub(guild: discord.Guild | None) -> discord.Embed:
    embed = discord.Embed(
        title=f"{visual.AXOLOTL} Axolotl BR",
        description="sua comunidade na internet desde 2020, de player pra player.",
        color=visual.PRIMARY,
    )
    embed.add_field(
        name="comunidade",
        value=f"jogar, criar e conectar. {_desde_2020(guild)}.",
        inline=False,
    )
    if guild is not None:
        humanos = sum(1 for m in guild.members if not m.bot)
        bots = sum(1 for m in guild.members if m.bot)
        embed.add_field(
            name="discord",
            value=(
                f"**{guild.name}** — {len(guild.members)} membros "
                f"({humanos} players, {bots} bots) · "
                f"{len(guild.text_channels)} chats · {len(guild.voice_channels)} calls"
            ),
            inline=False,
        )
    embed.add_field(name="site", value=SITE_URL, inline=False)
    embed.add_field(
        name="projetos",
        value="\n".join(f"**{nome}** — {desc}" for nome, desc in PROJETOS),
        inline=False,
    )
    embed.set_footer(text=visual.FOOTER)
    return embed


class Servidor(commands.Cog, name="Servidor"):
    """hub do servidor + player completo."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ─── >server ───
    @commands.command(name="server")
    async def server(self, ctx: commands.Context):
        """o hub do servidor."""
        await ctx.send(embed=_embed_hub(ctx.guild))

    # ─── /server ───
    @app_commands.command(name="server", description="o hub do servidor.")
    async def server_slash(self, interaction: discord.Interaction):
        """versão slash do >server."""
        await interaction.response.send_message(embed=_embed_hub(interaction.guild))

    # ─── >player ───
    @commands.command(name="player", aliases=["perfil"])
    async def player(self, ctx: commands.Context, membro: discord.Member = None):
        """veja o player completo (nível, deadlock, economia, coleção)."""
        await ctx.send(embed=await _montar_perfil(membro or ctx.author))

    # ─── /player ───
    @app_commands.command(name="player", description="veja o player completo.")
    @app_commands.describe(membro="ver o player de outro membro (opcional)")
    async def player_slash(
        self, interaction: discord.Interaction, membro: discord.Member | None = None
    ):
        """versão slash do >player."""
        await interaction.response.defer()
        await interaction.followup.send(
            embed=await _montar_perfil(
                membro or interaction.user  # type: ignore[arg-type]
            )
        )


BARRA_CHEIA = "█"
BARRA_VAZIA = "░"
BARRA_CELULAS = 10

# mesma ordem da loja: raridade mais alta = numero maior.
ORDEM_RAR = {"comum": 0, "incomum": 1, "raro": 2, "épico": 3, "lendário": 4}

# utc-3 fixo, mesmo do resto do bot.
TZ = datetime.timezone(datetime.timedelta(hours=-3))


async def _montar_perfil(membro: discord.Member) -> discord.Embed:
    # leituras independentes primeiro, tudo junto.
    hoje = datetime.datetime.now(TZ).date().isoformat()
    (xp, nivel), (dima, amet, aura), colecao, (pv, pd, pe), (nap, nvit), doces, ultimo_daily, feitas, (sdias, _) = await asyncio.gather(
        asyncio.to_thread(data.buscar_xp, membro.id),
        asyncio.to_thread(data.buscar_saldo, membro.id),
        asyncio.to_thread(data.buscar_colecao, membro.id),
        asyncio.to_thread(data.buscar_ptp, membro.id),
        asyncio.to_thread(data.buscar_bet, membro.id),
        asyncio.to_thread(data.buscar_doces, membro.id),
        asyncio.to_thread(data.buscar_daily, membro.id),
        asyncio.to_thread(data.feitas_no_dia, membro.id, hoje),
        asyncio.to_thread(data.buscar_streak, membro.id),
    )
    xp_prox = data.xp_para_proximo(nivel)
    celulas = int((xp / xp_prox) * BARRA_CELULAS)
    progresso = BARRA_CHEIA * celulas + BARRA_VAZIA * (BARRA_CELULAS - celulas)

    embed = discord.Embed(
        title=f"👤 player {membro.display_name}",
        description=f"nível **{nivel}** · `{xp}/{xp_prox}`\n`{progresso}`",
        color=visual.PRIMARY,
    )

    # deadlock: so se vinculado, com heroi top junto.
    steam = await asyncio.to_thread(data.buscar_deadlock, membro.id)
    if steam is None:
        embed.add_field(
            name="🎮 deadlock", value="não vinculado — usa `>vincular`.", inline=False
        )
    else:
        try:
            rank = await asyncio.to_thread(deadlock_api.buscar_rank, steam)
            ranks = await asyncio.to_thread(deadlock_api.buscar_ranks)
            tier = int(rank.get("rank", 0) or 0)
            nome = ranks.get(tier, "Obscurus")
            # texto em pt + romano igual o >rank e o >stats.
            rank_txt = deadlock_api.info_rank(rank, deadlock_api.NOMES_PT)["rank_txt"]
            perfil = await asyncio.to_thread(deadlock_api.buscar_steam_profile, steam)
            persona = perfil.get("personaname") or f"steam {steam}"
            linha = f"{visual.deadlock_rank_emoji(nome)}{persona} · {rank_txt}"
            topo = await asyncio.to_thread(deadlock_api.buscar_hero_stats, steam)
            if topo:
                melhor = max(topo, key=lambda h: int(h.get("matches_played", 0) or 0))
                heroes = await asyncio.to_thread(deadlock_api.buscar_heroes)
                hnome = heroes.get(int(melhor.get("hero_id", 0) or 0), "heroi")
                linha += (
                    f"\nherói top: {visual.deadlock_hero_emoji(hnome)}{hnome} "
                    f"({melhor.get('matches_played', 0)} partidas, "
                    f"{melhor.get('wins', 0)} vitórias)"
                )
            embed.add_field(name="🎮 deadlock", value=linha, inline=False)
        except deadlock_api.DeadlockAPIError:
            embed.add_field(name="🎮 deadlock", value="api fora do ar agora.", inline=False)

    daily = "já resgatado" if ultimo_daily == hoje else "disponível!"
    embed.add_field(
        name="💎 economia",
        value=f"{visual.DIAMANTE} {dima} · {visual.AMETHYST} {amet} · 🍬 {doces}"
        + (f" · aura {aura}" if aura else "")
        + f"\ndaily: {daily}",
        inline=False,
    )

    # colecao com o mais raro em destaque. nomes bonitos vêm da loja.
    from cogs.economia import AXOLOTLS, ALIAS_AXOLOTL

    if colecao:
        total = sum(q for _, q in colecao)
        itens = [(ALIAS_AXOLOTL.get(a, a), q) for a, q in colecao]
        raro = max(
            itens,
            key=lambda c: (ORDEM_RAR.get(AXOLOTLS.get(c[0], {}).get("rar", ""), -1), c[1]),
        )
        nome_raro = AXOLOTLS.get(raro[0], {"nome": raro[0], "rar": "?"})
        top = sorted(itens, key=lambda c: c[1], reverse=True)[:3]
        embed.add_field(
            name="🪸 coleção",
            value=f"{len(itens)}/{len(AXOLOTLS)} espécies · {total} no total\n"
            f"mais raro: **{nome_raro['nome']}** ({nome_raro['rar']}) x{raro[1]}\n"
            + ", ".join(f"{a} x{q}" for a, q in top),
            inline=False,
        )
    else:
        embed.add_field(name="🪸 coleção", value="vazia — gira com `>roll`.", inline=False)

    # jogos: ptp + bet + diarias de hoje.
    total_ptp = pv + pd + pe
    if total_ptp:
        winrate = round(pv / total_ptp * 100)
        linha_ptp = f"**{pv}**V **{pd}**D **{pe}**E · {winrate}%"
    else:
        linha_ptp = "sem jogada — `>ptp`."
    if nap:
        taxa = round(nvit / nap * 100)
        linha_bet = f"**{nap}** apostas · **{nvit}** vitórias ({taxa}%)"
    else:
        linha_bet = "sem aposta — `>bet`."
    embed.add_field(
        name="🎲 jogos",
        value=f"ptp: {linha_ptp}\nbet: {linha_bet}\ndiárias: **{len(feitas)}/3** hoje · 🔥 **{sdias}**",
        inline=False,
    )

    # servidor: so faz sentido dentro do servidor.
    if isinstance(membro, discord.Member) and membro.joined_at is not None:
        entrou = membro.joined_at.strftime("%d/%m/%Y")
        cargos = [c for c in membro.roles if not c.is_default()]
        linha = f"aqui desde **{entrou}**"
        if cargos:
            linha += f" · cargo top **{max(cargos, key=lambda c: c.position).name}**"
        embed.add_field(name="🖥️ servidor", value=linha, inline=False)

    embed.set_thumbnail(url=membro.display_avatar.url)
    embed.set_footer(text=visual.FOOTER)
    return embed


async def setup(bot: commands.Bot):
    await bot.add_cog(Servidor(bot))
