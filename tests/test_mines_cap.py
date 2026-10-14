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
