# a ajuda monta botoes por secao: titulo repetido = custom_id
# repetido = discord rejeita o envio com 400. teste anti-regressao.
# roda com: pytest tests/ (na raiz do bot).

from collections import Counter


def _carregar_tudo():
    import asyncio

    import main

    async def t():
        for cog in main.COGS:
            if cog not in main.bot.extensions:
                await main.bot.load_extension(cog)
        return main

    return asyncio.run(t())


def _ids(view):
    return [
        c.get("custom_id") for row in view.to_components() for c in row["components"]
    ]


def test_ajuda_sem_secao_duplicada():
    main = _carregar_tudo()
    titulos = [t for t, _ in main._linhas_ajuda({})]
    dup = [k for k, n in Counter(titulos).items() if n > 1]
    assert not dup, dup


def test_ajuda_sem_botao_duplicado():
    main = _carregar_tudo()
    v = main.AjudaView(main._linhas_ajuda({}))
    ids = _ids(v)
    assert None not in ids
    dup = [k for k, n in Counter(ids).items() if n > 1]
    assert not dup, dup


def test_views_sem_botao_duplicado():
    main = _carregar_tudo()
    from cogs import bet, deadlock, economia

    views = [
        bet.BetView(1, "slots", "dima", 100),
        bet.MinesView(1),
        economia.CaixaView(1, False),
        economia.LojaView([("Auras", None), ("Doces", None), ("Caixas", None)]),
        deadlock.VincularView(),
    ]
    for v in views:
        ids = _ids(v)
        assert None not in ids, type(v).__name__
        dup = [k for k, n in Counter(ids).items() if n > 1]
        assert not dup, (type(v).__name__, dup)
