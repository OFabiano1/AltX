# ─── conexao por thread ───

# o banco reaproveita a conexao da thread em vez de abrir uma por operacao.
# isso garante que reaproveitar nao vaza transacao nem mistura threads.

import threading

import pytest


def test_mesma_thread_reaproveita_conexao(banco):
    with banco._conectar() as a:
        pass
    with banco._conectar() as b:
        pass
    assert a is b


def test_threads_diferentes_tem_conexoes_proprias(banco):
    vistas = []

    def pega():
        with banco._conectar() as c:
            vistas.append(c)

    t = threading.Thread(target=pega)
    t.start()
    t.join()
    with banco._conectar() as minha:
        pass
    assert vistas[0] is not minha


def test_erro_faz_rollback_e_conexao_segue_util(banco):
    banco.adicionar_diamantes(1, 50)
    with pytest.raises(RuntimeError):
        with banco._conectar() as conn:
            conn.execute("UPDATE economia SET diamantes = 0 WHERE user_id = 1")
            raise RuntimeError("falha no meio")
    # o update morreu no rollback e a conexao da thread continua boa.
    assert banco.buscar_saldo(1)[0] == 50
    assert banco.adicionar_diamantes(1, 5) == 55
