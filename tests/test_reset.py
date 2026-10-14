# reset total de um player: apaga tudo sem deixar resto.
# roda com: pytest tests/test_reset.py (na raiz do bot).


def test_reset_limpa_tudo(banco):
    uid = 424242
    banco.ganhar_xp(uid, 500)
    banco.adicionar_diamantes(uid, 1000)
    banco.adicionar_ametista(uid, 50)
    banco.ganhar_doces(uid, 99)
    banco.adicionar_axolotl(uid, "roxo")
    banco.dar_aura(uid, "brisa")
    banco.registrar_ptp(uid, "vitoria")
    banco.registrar_aposta(uid, True)
    banco.dar_buff(uid, "xp2", 3600)
    banco.salvar_mines(uid, "dima", 100, {1, 2, 3})
    banco.vincular_deadlock(uid, 12345)
    banco.salvar_mudae(uid, 1, 1, 9999999999.0)
    banco.marcar_feita(uid, "2099-01-01", "msg10")
    banco.salvar_streak(uid, 5, "2099-01-01")
    banco.somar_contador(uid, "2099-01-01", "msg", 10)

    apagados = banco.reset_usuario(uid)
    assert apagados > 0

    assert banco.buscar_xp(uid) == (0, 1)
    assert banco.buscar_saldo(uid) == (0, 0, None)
    assert banco.buscar_doces(uid) == 0
    assert banco.buscar_colecao(uid) == []
    assert banco.auras_usuario(uid) == []
    assert banco.buscar_ptp(uid) == (0, 0, 0)
    assert banco.buscar_bet(uid) == (0, 0)
    assert banco.buff_ativo(uid, "xp2") == 0
    assert banco.buscar_mines(uid) is None
    assert banco.buscar_deadlock(uid) is None
    assert banco.buscar_streak(uid) == (0, "")
    assert banco.feitas_no_dia(uid, "2099-01-01") == []


def test_reset_id_sem_nada_retorna_zero(banco):
    assert banco.reset_usuario(999999) == 0
