import asyncio
import datetime
import logging
import os
import re

import discord
from discord.ext import commands

import data
import visual

log = logging.getLogger("alt.auto_response")

# o link do CDN do Discord carrega assinatura `ex=`/`hm=` e expira,
# virando 404 depois de um tempo. Configurar por env permite trocar sem
# deploy. Vazio = repost desativado.
REPOST_GIF = os.getenv("REPOST_GIF", "")
REPOST_GIF = REPOST_GIF.strip()

# utc-3 fixo, mesmo do resto do bot.
TZ = datetime.timezone(datetime.timedelta(hours=-3))

# oi no chat: so saudacao sozinha (oi, ola + bom/boa dia/tarde/noite/madrugada).
OI_RE = re.compile(
    r"^(o+i+|ol[áa]|bom dia|boa tarde|boa noite|boa madrugada)[?!.,]*$",
    re.IGNORECASE,
)


def saudacao_hora(hora: int) -> str:
    """saudacao pelo horario: 6-12 bom dia, 12-18 boa tarde, 18-24 boa noite, 0-6 boa madrugada."""
    if 6 <= hora < 12:
        return "bom dia"
    if 12 <= hora < 18:
        return "boa tarde"
    if 18 <= hora < 24:
        return "boa noite"
    return "boa madrugada"


class AutoResponse(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        if not REPOST_GIF:
            log.info("REPOST_GIF nao definido — repost automatico desativado")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # ignora mensagens do próprio bot
        if message.author == self.bot.user:
            return

        # responde W com um emote da lista (personalidade do bot).
        if message.content.strip().lower() == "w":
            await message.channel.send(f"W {visual.emote()}")

        # oi do dia: responde 1x por dia por pessoa. o contador
        # mora no banco, entao sobrevive a restart. a saudacao
        # segue o horario: oi de manha recebe bom dia.
        if OI_RE.match(message.content.strip()):
            agora = datetime.datetime.now(TZ)
            saudacao = saudacao_hora(agora.hour)
            total = await asyncio.to_thread(
                data.somar_contador, message.author.id, agora.date().isoformat(), "oi", 1
            )
            if total == 1:
                await message.channel.send(
                    f"{visual.AXOLOTL} {saudacao}, {message.author.mention}! {visual.emote()}"
                )

        # repost do gif automaticamente
        if REPOST_GIF and REPOST_GIF in message.content:
            await message.channel.send(REPOST_GIF)


async def setup(bot):
    await bot.add_cog(AutoResponse(bot))
