# ─── revisao 3.0.2 ───

# cada teste trava um bug achado na revisao do bot inteiro.

import ast
import asyncio
import datetime
import pathlib

RAIZ = pathlib.Path(__file__).parent.parent


def test_daily_vira_a_meia_noite_de_brasilia(monkeypatch):
    # era utc: o daily virava as 21h e o >player mostrava "disponivel" errado.
    from cogs import economia

    class Relogio(datetime.datetime):
        @classmethod
        def now(cls, tz=None):
            # 22h de brasilia = 01h utc do dia seguinte.
            return datetime.datetime(2026, 11, 10, 1, 0, tzinfo=datetime.timezone.utc).astimezone(tz)

    monkeypatch.setattr(economia, "datetime", Relogio)
    assert economia.hoje_daily() == "2026-11-09"


def test_github_so_posta_branch_principal():
    from cogs import github

    assert github._ramo_principal("refs/heads/main")
    assert github._ramo_principal("refs/heads/master")
    assert not github._ramo_principal("refs/heads/prism-tui")
    assert not github._ramo_principal("refs/tags/v1")
    # webhook manda a default_branch do repo.
    assert github._ramo_principal("refs/heads/dev", "dev")
    assert not github._ramo_principal("refs/heads/main", "dev")


def test_nenhum_await_em_funcao_sincrona_do_banco():
    # `await data.salvar_ticket_dono(...)` quebrava todo ticket: data.py e sincrono.
    funcoes_banco = {
        n.name
        for n in ast.parse((RAIZ / "data.py").read_text(encoding="utf-8")).body
        if isinstance(n, ast.FunctionDef)
    }
    erros = []
    for arq in [RAIZ / "main.py", *sorted((RAIZ / "cogs").glob("*.py"))]:
        for n in ast.walk(ast.parse(arq.read_text(encoding="utf-8"))):
            if (
                isinstance(n, ast.Await)
                and isinstance(n.value, ast.Call)
                and isinstance(n.value.func, ast.Attribute)
                and isinstance(n.value.func.value, ast.Name)
                and n.value.func.value.id == "data"
                and n.value.func.attr in funcoes_banco
            ):
                erros.append(f"{arq.name}:{n.lineno} await data.{n.value.func.attr}")
    assert not erros, erros


def test_textos_sem_endereco_morto_nem_xingamento():
    # axolotlbr.xyz e AxolotlSMP.enxada.host nao resolvem; "baitola" e xingamento.
    proibidos = ("axolotlbr.xyz", "enxada.host", "baitola", "cargos passam", "poder passivo")
    for arq in [RAIZ / "main.py", *sorted((RAIZ / "cogs").glob("*.py"))]:
        texto = arq.read_text(encoding="utf-8").lower()
        for p in proibidos:
            assert p not in texto, f"{arq.name}: {p}"


def test_mudae_reconexao_nao_duplica_lembrete(banco):
    from cogs import mudae

    class BotFake:
        pass

    async def t():
        cog = mudae.Mudae(BotFake())
        banco.salvar_mudae(7, 1, 1, __import__("time").time() + 600)
        await cog.on_ready()
        primeiro = cog.timers[7]
        await cog.on_ready()  # reconexao
        assert cog.timers[7] is primeiro
        cog.cog_unload()

    asyncio.run(t())


def test_mudae_com_rolls_sobrando_nao_agenda():
    from cogs import mudae

    assert mudae.parse_mudae("you have 3 rolls left") == (3, None)
