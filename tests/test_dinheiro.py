# fluxos que mexem com dinheiro: se quebrar aqui, alguem perde saldo.
# roda com: pytest tests/ (na raiz do bot).

import pytest


def test_daily_1x_por_dia(banco):
    ok, dima, amet = banco.tentar_daily(1, 100, 2, "2099-01-01")
    assert ok and (dima, amet) == (100, 2)
    ok, _, _ = banco.tentar_daily(1, 100, 2, "2099-01-01")
    assert not ok
    ok, _, _ = banco.tentar_daily(1, 100, 2, "2099-01-02")
    assert ok


def test_transferir(banco):
    banco.adicionar_diamantes(1, 100)
    ok, s1, s2 = banco.transferir_diamantes(1, 2, 40)
    assert ok and (s1, s2) == (60, 40)
    # insuficiente nao move nada
    ok, s1, s2 = banco.transferir_diamantes(1, 2, 999)
    assert not ok and (s1, s2) == (60, 40)
    # zero e pra si mesmo negam
    assert banco.transferir_diamantes(1, 2, 0)[0] is False
    assert banco.transferir_diamantes(1, 1, 10)[0] is False


def test_saldo_nunca_negativo(banco):
    assert banco.adicionar_diamantes(1, 50) == 50
    assert banco.adicionar_diamantes(1, -999) == 0
    assert banco.adicionar_ametista(1, -1) == 0


def test_gastar_doces(banco):
    banco.ganhar_doces(1, 50)
    assert banco.gastar_doces(1, 30) == (True, 20)
    assert banco.gastar_doces(1, 30) == (False, 20)
    assert banco.gastar_doces(1, 20) == (True, 0)
    assert banco.gastar_doces(1, 0)[0] is False


def test_buffs(banco):
    banco.dar_buff(1, "xp2", 3600)
    assert 3500 < banco.buff_ativo(1, "xp2") <= 3600
    banco.dar_buff(1, "xp2", 3600)  # estende, nao reseta
    assert banco.buff_ativo(1, "xp2") > 3600
    assert banco.buff_ativo(1, "dima2") == 0
    banco.dar_buff(1, "dima2", 0)
    assert banco.buffs_ativos(1).keys() == {"xp2"}


def test_apostas(banco):
    banco.registrar_aposta(1, True)
    banco.registrar_aposta(1, False)
    assert banco.buscar_bet(1) == (2, 1)
    assert banco.buscar_bet(2) == (0, 0)


def test_ptp_invalido_quebra_alto(banco):
    with pytest.raises(KeyError):
        banco.registrar_ptp(1, "tesoura")


def test_mines_persiste_e_reembolsa(banco):
    banco.salvar_mines(1, "dima", 100, {1, 2, 3})
    assert banco.buscar_mines(1)["valor"] == 100
    jogo, nova = banco.abrir_mines(1, 5)
    assert (jogo["abertos"], nova) == ({5}, True)
    jogo, nova = banco.abrir_mines(1, 5)
    assert (jogo["abertos"], nova) == ({5}, False)
    assert banco.abrir_mines(2, 5) == (None, False)
    # boot: lista, reembolsa, remove
    pendentes = banco.listar_mines()
    assert len(pendentes) == 1
    banco.adicionar_diamantes(1, 1000)
    for jogo in pendentes:
        banco.adicionar_diamantes(jogo["user_id"], jogo["valor"])
        banco.remover_mines(jogo["user_id"])
    assert banco.buscar_saldo(1)[0] == 1100
    assert banco.listar_mines() == []


def test_backup_e_restore(banco, tmp_path):
    banco.adicionar_diamantes(1, 777)
    arq = banco.backup(keep=2)
    assert arq is not None and arq.exists()
    assert banco.verificar_backup(arq) is True
    assert banco.verificar_backup(tmp_path / "nao-existe.db") is False
    # retencao: 2 velhos + backup novo (keep=2) = sobram 2
    (banco.BACKUP_DIR / "alt-20200101-0000.db").touch()
    (banco.BACKUP_DIR / "alt-20200202-0000.db").touch()
    banco.backup(keep=2)
    sobraram = sorted(p.name for p in banco.BACKUP_DIR.glob("alt-*.db"))
    assert len(sobraram) == 2 and "alt-20200101-0000.db" not in sobraram


def test_snapshot_tem_tudo(banco):
    banco.ganhar_xp(1, 150)
    banco.adicionar_diamantes(1, 10)
    banco.adicionar_axolotl(1, "roxo")
    s = banco.snapshot(1, "2099-01-01")
    assert (s["xp"], s["nivel"]) == banco.buscar_xp(1)
    assert (s["dima"], s["amet"], s["aura"]) == banco.buscar_saldo(1)
    assert s["colecao"] == banco.buscar_colecao(1)
    assert "buffs" in s and "steam" in s


def test_posicao(banco):
    assert banco.posicao_xp(99) is None
    banco.ganhar_xp(1, 500)
    banco.ganhar_xp(2, 100)
    assert banco.posicao_xp(1) == 1
    assert banco.posicao_xp(2) == 2
    assert banco.snapshot(1, "2099-01-01")["pos"] == 1


def test_cortar_diamantes(banco):
    banco.adicionar_diamantes(1, 101)
    banco.adicionar_diamantes(2, 50)
    afetados, antes, depois = banco.cortar_diamantes()
    assert (afetados, antes, depois) == (2, 151, 75)
    assert banco.buscar_saldo(1)[0] == 50
    assert banco.buscar_saldo(2)[0] == 25


def test_slots_puro():
    from cogs.bet import _girar, _premio_slots, _parse_aposta, PESOS, SIMBOLOS

    assert sum(PESOS) == 20 and len(SIMBOLOS) == 6
    assert _premio_slots(["7️⃣", "7️⃣", "7️⃣"], 10) == 100
    assert _premio_slots(["🍒", "🍒", "🍋"], 10) == 10
    assert _premio_slots(["🍒", "🍋", "⭐"], 10) == 0
    assert _parse_aposta("dima", "67") == ("dima", 67)
    assert _parse_aposta("dima", "1001") == (None, 0)
    assert _parse_aposta("67", "") == ("dima", 67)
    assert len(_girar()) == 3


def test_mines_mult():
    from cogs.bet import _mult_mines, MINAS_TOTAL

    assert MINAS_TOTAL == 20
    assert _mult_mines(0, 3) == 1.0
    assert _mult_mines(1, 15) > _mult_mines(1, 3) > 1.0


def test_apostas_simultaneas(banco):
    """20 apostas de 100 com saldo pra 10: exatas 10 passam, nunca negativo."""
    import asyncio

    from cogs.bet import _cobrar

    banco.adicionar_diamantes(1, 1000)

    async def t():
        return await asyncio.gather(*[_cobrar(1, "dima", 100) for _ in range(20)])

    res = asyncio.run(t())
    assert sum(1 for ok, _ in res if ok) == 10
    assert banco.buscar_saldo(1)[0] == 0


class _RespFake:
    def __init__(self):
        self.edits = []
        self.deferred = 0
        self.follows = []

    async def defer(self):
        self.deferred += 1

    async def edit_message(self, **kw):
        self.edits.append(kw)

    async def send_message(self, *a, **k):
        pass


class _InterFake:
    def __init__(self, u):
        self.user = type("U", (), {"id": u})()
        self.response = _RespFake()
        self.follows = []

    async def edit_original_response(self, **kw):
        self.response.edits.append(kw)

    async def followup_send(self, *a, **k):
        self.follows.append((a, k))

    @property
    def followup(self):
        return self

    async def send(self, *a, **k):
        self.follows.append((a, k))


def test_mines_duplo_clique(banco):
    """3 cliques juntos no mesmo tile: sem deadlock, sem duplicar, jogo acaba."""
    import asyncio

    from cogs import bet

    async def t():
        banco.adicionar_diamantes(1, 1000)
        await bet._comecar_mines(1, "dima", 100)
        jogo = banco.buscar_mines(1)
        seguro = next(x for x in range(20) if x not in jogo["minas"])
        inters = [_InterFake(1) for _ in range(3)]
        await asyncio.wait_for(
            asyncio.gather(*[bet._cavar(i, 1, seguro) for i in inters]),
            timeout=20,
        )
        # 1 abriu + 2 tentaram sacar cedo: jogo segue vivo, sem deadlock
        assert banco.buscar_mines(1) is not None
        assert len(banco.buscar_mines(1)["abertos"]) == 1
        # todo clique confirmou na hora (defer), ninguem travou
        assert all(i.response.deferred == 1 for i in inters)
        # abre +2 e saca: ai sim acaba
        segs = [x for x in range(20) if x not in jogo["minas"] and x != seguro][:2]
        for s in segs:
            await bet._cavar(_InterFake(1), 1, s)
        await bet._sacar_nucleo(1, _InterFake(1))
        assert banco.buscar_mines(1) is None

    asyncio.run(t())


def test_minas_por_valor():
    from cogs.bet import _minas_por_valor

    assert _minas_por_valor(1) == 3
    assert _minas_por_valor(49) == 3
    assert _minas_por_valor(50) == 5
    assert _minas_por_valor(149) == 5
    assert _minas_por_valor(150) == 8
    assert _minas_por_valor(299) == 8
    assert _minas_por_valor(300) == 12
    assert _minas_por_valor(599) == 12
    assert _minas_por_valor(600) == 15
    assert _minas_por_valor(1000) == 15


def test_mines_minimo_saque(banco):
    """menos de 3 abertas: retirar nega e o jogo continua."""
    import asyncio

    from cogs import bet

    async def t():
        banco.adicionar_diamantes(1, 1000)
        await bet._comecar_mines(1, "dima", 100)
        jogo = banco.buscar_mines(1)
        assert len(jogo["minas"]) == 5  # 100 -> faixa 5
        seguro = next(x for x in range(20) if x not in jogo["minas"])
        i = _InterFake(1)
        await bet._cavar(i, 1, seguro)
        await bet._sacar_nucleo(1, i)
        assert banco.buscar_mines(1) is not None  # segue vivo
        assert any("3" in str(a) for a, _ in i.follows)
        segs = [x for x in range(20) if x not in jogo["minas"] and x != seguro][:2]
        for s in segs:
            await bet._cavar(_InterFake(1), 1, s)
        await bet._sacar_nucleo(1, i)
        assert banco.buscar_mines(1) is None  # com 3 sacou

    asyncio.run(t())
