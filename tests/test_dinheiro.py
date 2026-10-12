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
    assert banco.abrir_mines(1, 5)["abertos"] == {5}
    assert banco.abrir_mines(2, 5) is None
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


def test_posicao_e_recentes(banco):
    assert banco.posicao_xp(99) is None
    banco.ganhar_xp(1, 500)
    banco.ganhar_xp(2, 100)
    assert banco.posicao_xp(1) == 1
    assert banco.posicao_xp(2) == 2
    banco.dar_conquista(1, "nivel2", "x")
    banco.dar_conquista(1, "mil_dima", "x")
    assert banco.conquistas_recentes(1) == ["mil_dima", "nivel2"]
    assert banco.snapshot(1, "2099-01-01")["pos"] == 1


def test_conquistas_avaliar():
    from conquistas import avaliar, CONQUISTAS

    zero = {"nivel": 1}
    assert avaliar(zero) == []
    full = {
        "nivel": 10, "vinculado": True, "dima": 5000, "doces": 500,
        "tem_raro": True, "tem_lendario": True, "full": True,
        "apostas": 50, "vitorias": 20, "streak": 30,
        "feitas_hoje": 3, "ptp_total": 200, "daily_vez": True,
    }
    assert avaliar(full) == list(CONQUISTAS)
    assert avaliar({"nivel": 1, "ptp_total": 100}) == ["maratona_ptp"]
    assert avaliar({"nivel": 1, "daily_vez": True}) == ["primeiro_daily"]


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
