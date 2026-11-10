# isso aq mostra o perfil e a skin de um nick do minecraft (java).
# fonte real: api da mojang (nick -> uuid) + sessionserver (skin e capa).
# o desenho da skin vem do crafatar. so stdlib: urllib via asyncio.to_thread.

import asyncio
import base64
import json
import re
import urllib.error
import urllib.request

import discord
from discord import app_commands
from discord.ext import commands

import visual

# ─── fontes ───

MOJANG = "https://api.mojang.com/users/profiles/minecraft/"
SESSAO = "https://sessionserver.mojang.com/session/minecraft/profile/"
CRAFATAR = "https://crafatar.com"
TIMEOUT = 10
HEADERS = {"User-Agent": "ALT-bot/3.0 (+discord)"}

# regra do nick java: 3 a 16, letra, numero e _.
NICK_VALIDO = re.compile(r"^[A-Za-z0-9_]{3,16}$")


# ─── erro ───


class MinecraftAPIError(Exception):
    """mojang fora, timeout ou resposta quebrada."""


# ─── http ───


def _get_json(url: str) -> dict | None:
    """get sincrono. None = nao existe (404/204), erro de rede vira MinecraftAPIError."""
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            corpo = resp.read()
    except urllib.error.HTTPError as e:
        if e.code in (204, 404):
            return None
        raise MinecraftAPIError(f"http {e.code}") from e
    except Exception as e:
        raise MinecraftAPIError(type(e).__name__) from e
    if not corpo:
        return None
    try:
        dados = json.loads(corpo)
    except ValueError as e:
        raise MinecraftAPIError("json invalido") from e
    return dados if isinstance(dados, dict) else None


# ─── perfil ───


def uuid_com_hifen(uuid: str) -> str:
    u = uuid.replace("-", "")
    return f"{u[:8]}-{u[8:12]}-{u[12:16]}-{u[16:20]}-{u[20:]}"


def parse_texturas(sessao: dict) -> dict:
    """skin, modelo e capa do perfil da sessionserver (textures em base64)."""
    texturas: dict = {}
    for prop in sessao.get("properties") or []:
        if prop.get("name") == "textures":
            try:
                texturas = json.loads(base64.b64decode(prop.get("value") or ""))
            except ValueError:
                texturas = {}
            break
    t = texturas.get("textures") or {}
    skin = t.get("SKIN") or {}
    capa = t.get("CAPE") or {}
    https = lambda url: url.replace("http://", "https://", 1) if url else None  # noqa: E731
    return {
        "skin_url": https(skin.get("url")),
        # sem metadata e o braco largo (steve); "slim" e o fino (alex).
        "modelo": "slim" if (skin.get("metadata") or {}).get("model") == "slim" else "classico",
        "capa_url": https(capa.get("url")),
    }


def buscar_perfil(nick: str) -> dict | None:
    """perfil real do nick. None se o nick nao existe."""
    basico = _get_json(MOJANG + nick)
    if not basico or not basico.get("id"):
        return None
    uuid = basico["id"]
    sessao = _get_json(SESSAO + uuid) or {}
    return {"nome": basico.get("name") or nick, "uuid": uuid, **parse_texturas(sessao)}


# ─── embeds ───


def _embed_perfil(p: dict) -> discord.Embed:
    modelo = "slim (alex)" if p["modelo"] == "slim" else "clássico (steve)"
    embed = discord.Embed(
        title=p["nome"],
        url=f"https://namemc.com/profile/{p['uuid']}",
        description=(
            f"uuid `{uuid_com_hifen(p['uuid'])}`\n"
            f"modelo **{modelo}**\n"
            f"capa **{'tem' if p['capa_url'] else 'não tem'}**"
        ),
        color=visual.PRIMARY,
    )
    embed.set_thumbnail(url=f"{CRAFATAR}/avatars/{p['uuid']}?size=128&overlay")
    embed.set_footer(text=visual.FOOTER)
    return embed


def _embed_skin(p: dict) -> discord.Embed:
    links = []
    if p["skin_url"]:
        links.append(f"[baixar a skin]({p['skin_url']})")
    if p["capa_url"]:
        links.append(f"[baixar a capa]({p['capa_url']})")
    embed = discord.Embed(
        title=f"skin de {p['nome']}",
        url=f"https://namemc.com/profile/{p['uuid']}",
        description=" · ".join(links) or "usa a skin padrão do minecraft.",
        color=visual.PRIMARY,
    )
    embed.set_thumbnail(url=f"{CRAFATAR}/avatars/{p['uuid']}?size=128&overlay")
    embed.set_image(url=f"{CRAFATAR}/renders/body/{p['uuid']}?overlay&scale=10")
    embed.set_footer(text=visual.FOOTER)
    return embed


# ─── resposta comum ───


async def _perfil_ou_motivo(nick: str) -> tuple[dict | None, str | None]:
    """(perfil, None) ou (None, texto do erro pro chat)."""
    nick = (nick or "").strip()
    if not NICK_VALIDO.match(nick):
        return None, "nick inválido! são 3 a 16 letras, números ou `_`. ex: `>minecraft jeb_`."
    try:
        perfil = await asyncio.to_thread(buscar_perfil, nick)
    except MinecraftAPIError:
        return None, "a mojang não respondeu, tenta de novo em uns segundos."
    if perfil is None:
        return None, f"não achei ninguém com o nick **{nick}** no minecraft java."
    return perfil, None


class Minecraft(commands.Cog, name="Minecraft"):
    """perfil e skin de nick do minecraft."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ─── >minecraft ───
    @commands.command(name="minecraft")
    async def minecraft(self, ctx: commands.Context, nick: str = ""):
        """perfil de um nick do minecraft. ex: `>minecraft jeb_`."""
        async with ctx.typing():
            perfil, erro = await _perfil_ou_motivo(nick)
        if erro:
            await ctx.send(erro)
            return
        await ctx.send(embed=_embed_perfil(perfil))

    @app_commands.command(name="minecraft", description="perfil de um nick do minecraft.")
    @app_commands.describe(nick="nick do minecraft java")
    async def minecraft_slash(self, interaction: discord.Interaction, nick: str):
        await interaction.response.defer()
        perfil, erro = await _perfil_ou_motivo(nick)
        if erro:
            await interaction.followup.send(erro)
            return
        await interaction.followup.send(embed=_embed_perfil(perfil))

    # ─── >skin ───
    @commands.command(name="skin")
    async def skin(self, ctx: commands.Context, nick: str = ""):
        """skin inteira de um nick do minecraft. ex: `>skin jeb_`."""
        async with ctx.typing():
            perfil, erro = await _perfil_ou_motivo(nick)
        if erro:
            await ctx.send(erro.replace(">minecraft", ">skin"))
            return
        await ctx.send(embed=_embed_skin(perfil))

    @app_commands.command(name="skin", description="skin inteira de um nick do minecraft.")
    @app_commands.describe(nick="nick do minecraft java")
    async def skin_slash(self, interaction: discord.Interaction, nick: str):
        await interaction.response.defer()
        perfil, erro = await _perfil_ou_motivo(nick)
        if erro:
            await interaction.followup.send(erro.replace(">minecraft", "/skin"))
            return
        await interaction.followup.send(embed=_embed_skin(perfil))


async def setup(bot: commands.Bot):
    await bot.add_cog(Minecraft(bot))
