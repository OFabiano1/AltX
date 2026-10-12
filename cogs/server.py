# isso aq e o hub do servidor: comunidade, discord, site e projetos.
# so dado real: o do discord vem do guild, o resto e fato do dono.
# axolotl smp entra como projeto, ip so quando existir (sem numero inventado).

import asyncio
import datetime
import io
import logging

import discord
from discord import app_commands
from discord.ext import commands

import conquistas
import data
import deadlock_api
import player_card
import visual

log = logging.getLogger("alt.server")

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
        """veja o player: xp, economia e conquistas."""
        embed, arquivo = await _montar_perfil(membro or ctx.author)
        await ctx.send(embed=embed, file=arquivo)

    # ─── /player ───
    @app_commands.command(name="player", description="veja o player: xp, economia e conquistas.")
    @app_commands.describe(membro="ver o player de outro membro (opcional)")
    async def player_slash(
        self, interaction: discord.Interaction, membro: discord.Member | None = None
    ):
        """versão slash do >player."""
        await interaction.response.defer()
        embed, arquivo = await _montar_perfil(
            membro or interaction.user  # type: ignore[arg-type]
        )
        await interaction.followup.send(embed=embed, file=arquivo)

    # ─── >conquistas ───
    @commands.command(name="conquistas")
    async def conquistas_cmd(self, ctx: commands.Context, membro: discord.Member = None):
        """lista todas as conquistas e as suas desbloqueadas."""
        membro = membro or ctx.author
        minhas = set(await asyncio.to_thread(data.conquistas_usuario, membro.id))
        linhas = []
        for cid, info in conquistas.CONQUISTAS.items():
            marca = "✅" if cid in minhas else "⬜"
            linhas.append(f"{marca} {info['icone']} **{info['nome']}** — {info['desc']}")
        embed = discord.Embed(
            title=f"🏆 conquistas de {membro.display_name} ({len(minhas)}/{len(conquistas.CONQUISTAS)})",
            description="\n".join(linhas),
            color=visual.PRIMARY,
        )
        embed.set_footer(text=visual.FOOTER)
        await ctx.send(embed=embed)

    # ─── /conquistas ───
    @app_commands.command(name="conquistas", description="lista todas as conquistas.")
    @app_commands.describe(membro="ver as conquistas de outro membro (opcional)")
    async def conquistas_slash(
        self, interaction: discord.Interaction, membro: discord.Member | None = None
    ):
        """versão slash do >conquistas."""
        membro = membro or interaction.user
        minhas = set(
            await asyncio.to_thread(data.conquistas_usuario, membro.id)  # type: ignore[attr-defined]
        )
        linhas = []
        for cid, info in conquistas.CONQUISTAS.items():
            marca = "✅" if cid in minhas else "⬜"
            linhas.append(f"{marca} {info['icone']} **{info['nome']}** — {info['desc']}")
        embed = discord.Embed(
            title=f"🏆 conquistas de {membro.display_name} ({len(minhas)}/{len(conquistas.CONQUISTAS)})",
            description="\n".join(linhas),
            color=visual.PRIMARY,
        )
        embed.set_footer(text=visual.FOOTER)
        await interaction.response.send_message(embed=embed)


BARRA_CHEIA = "█"
BARRA_VAZIA = "░"
BARRA_CELULAS = 10

# utc-3 fixo, mesmo do resto do bot.
TZ = datetime.timezone(datetime.timedelta(hours=-3))


async def _montar_perfil(membro: discord.Member) -> tuple[discord.Embed, discord.File | None]:
    """player: xp + economia + conquistas + card. sem deadlock, colecao e jogos."""
    from cogs.economia import AXOLOTLS, ALIAS_AXOLOTL

    hoje = datetime.datetime.now(TZ).date().isoformat()
    # tudo numa conexao so: abre rapidin.
    snap = await asyncio.to_thread(data.snapshot, membro.id, hoje)
    xp, nivel = snap["xp"], snap["nivel"]
    dima, amet, aura = snap["dima"], snap["amet"], snap["aura"]
    colecao = snap["colecao"]
    nap, nvit = snap["apostas"], snap["vitorias"]
    doces = snap["doces"]
    ultimo_daily = snap["daily"]
    feitas = snap["feitas"]
    sdias = snap["streak"]
    pv, pd, pe = snap["ptp"]
    steam = snap["steam"]
    xp_prox = data.xp_para_proximo(nivel)
    celulas = int((xp / xp_prox) * BARRA_CELULAS)
    progresso = BARRA_CHEIA * celulas + BARRA_VAZIA * (BARRA_CELULAS - celulas)

    # conquistas: avalia o snapshot e desbloqueia o que bateu.
    tem_lendario = any(
        AXOLOTLS.get(ALIAS_AXOLOTL.get(a, a), {}).get("rar") == "lendário"
        for a, _ in colecao
    )
    snap_conq = {
        "nivel": nivel,
        "vinculado": steam is not None,
        "dima": dima,
        "amet": amet,
        "doces": doces,
        "especies": len(colecao),
        "tem_lendario": tem_lendario,
        "apostas": nap,
        "vitorias": nvit,
        "streak": sdias,
        "feitas_hoje": len(feitas),
        "ptp_total": pv + pd + pe,
    }
    ja = set(await asyncio.to_thread(data.conquistas_usuario, membro.id))
    novas = []
    for cid in conquistas.avaliar(snap_conq):
        if cid not in ja and await asyncio.to_thread(
            data.dar_conquista, membro.id, cid, hoje
        ):
            novas.append(cid)
    desbloq = [c for c in conquistas.CONQUISTAS if c in ja or c in novas]

    embed = discord.Embed(
        title=f"👤 player {membro.display_name}",
        description=f"nível **{nivel}** · `{xp}/{xp_prox}`\n`{progresso}`",
        color=visual.PRIMARY,
    )

    daily = "já resgatado" if ultimo_daily == hoje else "disponível!"
    nomes_buff = {"xp2": "2x xp", "dima2": "2x dima"}
    linha_buff = " · ".join(
        f"**{nomes_buff.get(t, t)}** ({s // 60}min)" if s >= 60 else f"**{nomes_buff.get(t, t)}** ({s}s)"
        for t, s in snap["buffs"].items()
        if s > 0
    )
    embed.add_field(
        name="💎 economia",
        value=f"{visual.DIAMANTE} {dima} · {visual.AMETHYST} {amet} · 🍬 {doces}"
        + (f" · aura {aura}" if aura else "")
        + f"\ndaily: {daily}"
        + (f"\n⚡ {linha_buff}" if linha_buff else ""),
        inline=False,
    )

    if desbloq:
        valor_conq = "\n".join(conquistas.linha(c) for c in desbloq)
    else:
        valor_conq = "nenhuma ainda — joga pra desbloquear!"
    if novas:
        valor_conq += "\n\n🎉 novas: " + ", ".join(conquistas.linha(c) for c in novas)
    embed.add_field(
        name=f"🏆 conquistas ({len(desbloq)}/{len(conquistas.CONQUISTAS)})",
        value=valor_conq,
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

    # card com imagem. se falhar, o texto segue sozinho.
    arquivo = None
    try:
        destaques = [conquistas.CONQUISTAS[c]["nome"] for c in novas[:3]]
        png = await asyncio.wait_for(
            asyncio.to_thread(
                player_card.render_player,
                nivel,
                xp,
                xp_prox,
                len(desbloq),
                len(conquistas.CONQUISTAS),
                destaques,
                dima,
                amet,
                doces,
            ),
            timeout=10,
        )
        arquivo = discord.File(io.BytesIO(png), filename="player.png")
        embed.set_image(url="attachment://player.png")
    except Exception:
        log.exception("player: card falhou, vai so texto")

    embed.set_thumbnail(url=membro.display_avatar.url)
    embed.set_footer(text=visual.FOOTER)
    return embed, arquivo


async def setup(bot: commands.Bot):
    await bot.add_cog(Servidor(bot))
