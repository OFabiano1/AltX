# cap do mines: sem teto um hit paga 100k x e quebra a economia.
# roda com: pytest tests/test_mines_cap.py (na raiz do bot).

def test_mult_nunca_passa_de_10x():
    from cogs.bet import _mult_mines

    assert _mult_mines(8, 5) == 10.0
    assert _mult_mines(8, 12) == 10.0
    assert _mult_mines(5, 15) == 10.0
    assert _mult_mines(1, 3) <= 10.0


def test_premio_nunca_passa_de_5k():
    from cogs.bet import _premio_mines

    assert _premio_mines(1000, 5, 15) == 5000
    assert _premio_mines(100, 8, 5) == 1000


def test_casa_sempre_ganha():
    # ev de sacar com k pedras = p(k seguras) * multi. tem que ser < 1 em toda faixa.
    from math import comb
    from cogs.bet import FAIXAS_MINA, MINAS_TOTAL, _minimo_saque, _mult_mines

    for _, minas in FAIXAS_MINA:
        for k in range(_minimo_saque(minas), MINAS_TOTAL - minas + 1):
            p = comb(MINAS_TOTAL - minas, k) / comb(MINAS_TOTAL, k)
            assert p * _mult_mines(k, minas) <= 0.75 + 1e-9, (minas, k)


def test_minimo_saque_sobe_com_bomba():
    from cogs.bet import _minimo_saque

    assert [_minimo_saque(m) for m in (3, 5, 8, 12, 15)] == [3, 3, 3, 5, 6]
