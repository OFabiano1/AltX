# isso aq tira backup diario do banco com retencao e checa integridade.
# sem backup, perder saldo, colecao e xp nao tem volta.

import asyncio
import datetime
import logging

import discord
from discord import app_commands
from discord.ext import commands, tasks

import data
import visual

log = logging.getLogger("alt.backup")

# utc-3 fixo, mesmo do resto do bot. 4h: horario morto.
TZ = datetime.timezone(datetime.timedelta(hours=-3))
HORA = datetime.time(hour=4, minute=0, tzinfo=TZ)


async def _fazer_backup() -> str:
    """roda backup + verify. devolve linha de relato."""
    arq = await asyncio.to_thread(data.backup, 7)
    if arq is None:
        return "sem banco ainda, nada pra guardar."
    ok = await asyncio.to_thread(data.verificar_backup, arq)
    return (
        f"backup `{arq.name}` ok (integrity_check passou)."
        if ok
        else f"backup `{arq.name}` FALHOU no integrity_check!"
    )


class Backup(commands.Cog, name="Backup"):
    """backup diario do banco."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.backup_diario.is_running():
            self.backup_diario.start()
            log.info("backup: loop diario 04:00 armado")

    @tasks.loop(time=HORA)
    async def backup_diario(self):
        log.info("backup: %s", await _fazer_backup())

    @backup_diario.before_loop
    async def before_backup(self):
        await self.bot.wait_until_ready()

    # ─── >backup ───
    @commands.command(name="backup")
    @commands.has_permissions(administrator=True)
    async def backup(self, ctx: commands.Context):
        """[admin] tira backup do banco agora."""
        await ctx.send(f"💾 {await _fazer_backup()}")

    # ─── /backup ───
    @app_commands.command(name="backup", description="[admin] tira backup do banco agora.")
    @app_commands.checks.has_permissions(administrator=True)
    async def backup_slash(self, interaction: discord.Interaction):
        """versão slash do >backup."""
        await interaction.response.defer()
        await interaction.followup.send(f"💾 {await _fazer_backup()}")

    def cog_unload(self):
        if self.backup_diario.is_running():
            self.backup_diario.cancel()


async def setup(bot: commands.Bot):
    await bot.add_cog(Backup(bot))
