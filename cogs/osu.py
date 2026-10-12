# isso aq sorteia uma musica do osu! (beatmap aleatorio, ranked).
# fonte: mirror.hinamizawa.ai (gratis, sem auth, sem token).
# so stdlib: urllib roda via asyncio.to_thread no cog, sem dep nova.

import asyncio
import json
import urllib.parse
import urllib.request

import discord
from discord import app_commands
from discord.ext import commands

import visual

BASE = "https://mirror.hinamizawa.ai"
TIMEOUT = 15

HEADERS = {"User-Agent": "ALT-bot/1.0 (+discord)"}

# modo osu! -> id numerico da api.
MODOS = {"osu": 0, "taiko": 1, "catch": 2, "mania": 3}


# ─── erro ───


class OsuAPIError(Exception):
    """falha falando com o mirror (http, timeout, json)."""


# ─── http ───


def _get_json(caminho: str, query: dict | None = None) -> dict:
    """get sincrono, levanta OsuAPIError com motivo curto."""
    qs = f"?{urllib.parse.urlencode(query)}" if query else ""
    url = f"{BASE}{caminho}{qs}"
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            dados = json.load(resp)
    except urllib.error.HTTPError as e:
        raise OsuAPIError(f"http {e.code}") from e
    except (urllib.error.URLError, TimeoutError, ValueError) as e:
        raise OsuAPIError(f"{type(e).__name__}") from e
    except Exception as e:
        raise OsuAPIError(f"{type(e).__name__}") from e
    if not isinstance(dados, dict):
        raise OsuAPIError("resposta invalida")
    return dados


# ─── sorteio ───


def _mmss(segundos: int) -> str:
    return f"{segundos // 60}:{segundos % 60:02d}"


def sortear_mapa(mode: int = 0) -> dict:
    """1 dificuldade aleatoria (ranked). dict enxuto pro embed."""
    dados = _get_json(
        "/v3/osu/beatmaps/random", {"amount": 1, "status": "ranked", "mode": mode}
    )
    resultados = dados.get("results") or []
    if not resultados or not isinstance(resultados[0], dict):
        raise OsuAPIError("sem resultado")
    r = resultados[0]
    bs = r.get("beatmapset") or {}
    set_id = int(bs.get("id") or r.get("beatmapset_id") or 0)
    if not set_id:
        raise OsuAPIError("sem resultado")
    try:
        stars = float(r.get("difficulty_rating") or 0)
    except (TypeError, ValueError):
        stars = 0.0
    try:
        bpm = float(bs.get("bpm") or r.get("bpm") or 0)
    except (TypeError, ValueError):
        bpm = 0.0
    try:
        segundos = int(r.get("total_length") or 0)
    except (TypeError, ValueError):
        segundos = 0
    return {
        "artista": bs.get("artist_unicode") or bs.get("artist") or "?",
        "titulo": bs.get("title_unicode") or bs.get("title") or "?",
        "mapper": bs.get("creator") or "?",
        "bpm": bpm,
        "duracao": _mmss(segundos),
        "stars": stars,
        "diff": r.get("version") or "?",
        "set_id": set_id,
        "url": f"https://osu.ppy.sh/beatmapsets/{set_id}",
        "capa": f"https://assets.ppy.sh/beatmaps/{set_id}/covers/list.jpg",
    }


def _embed_mapa(m: dict, modo_nome: str) -> discord.Embed:
    embed = discord.Embed(
        title=f"{m['artista']} — {m['titulo']}",
        url=m["url"],
        description=(
            f"mapper **{m['mapper']}**\n"
            f"diff **{m['diff']}** · ⭐ **{m['stars']:.2f}**\n"
            f"bpm **{m['bpm']:.0f}** · ⏱️ **{m['duracao']}** · modo **{modo_nome}**"
        ),
        color=visual.PRIMARY,
    )
    embed.set_thumbnail(url=m["capa"])
    embed.set_footer(text=f"abre o link pra ouvir e baixar • {visual.FOOTER}")
    return embed


class Osu(commands.Cog, name="osu!"):
    """musica aleatoria do osu!."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ─── >osu ───
    @commands.command(name="osu")
    async def osu(self, ctx: commands.Context, modo: str = "osu"):
        """sorteia uma musica ranked do osu! ex: `>osu mania`."""
        mode_nome = (modo or "osu").lower()
        if mode_nome not in MODOS:
            await ctx.send(
                f"modo inválido! usa: {', '.join(f'`>osu {m}`' for m in MODOS)}"
            )
            return
        try:
            async with ctx.typing():
                m = await asyncio.to_thread(sortear_mapa, MODOS[mode_nome])
        except OsuAPIError:
            await ctx.send("o mirror do osu! tá fora do ar, tenta de novo em uns segundos.")
            return
        await ctx.send(embed=_embed_mapa(m, mode_nome))

    # ─── /osu ───
    @app_commands.command(name="osu", description="sorteia uma musica ranked do osu!.")
    @app_commands.describe(modo="modo de jogo (padrão: osu)")
    @app_commands.choices(
        modo=[
            app_commands.Choice(name="osu", value="osu"),
            app_commands.Choice(name="taiko", value="taiko"),
            app_commands.Choice(name="catch", value="catch"),
            app_commands.Choice(name="mania", value="mania"),
        ]
    )
    async def osu_slash(self, interaction: discord.Interaction, modo: str = "osu"):
        """versão slash do >osu."""
        if modo not in MODOS:
            modo = "osu"
        await interaction.response.defer()
        try:
            m = await asyncio.to_thread(sortear_mapa, MODOS[modo])
        except OsuAPIError:
            await interaction.followup.send(
                "o mirror do osu! tá fora do ar, tenta de novo em uns segundos."
            )
            return
        await interaction.followup.send(embed=_embed_mapa(m, modo))


async def setup(bot: commands.Bot):
    await bot.add_cog(Osu(bot))
