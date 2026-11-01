# card do >player: renderiza o png padrao de moedas (dima + ametista).
# roda com: pytest tests/test_player_card.py (na raiz do bot).

from player_card import render_player


def test_render_player_padrao():
    png = render_player(
        nivel=2,
        pos=None,
        xp=10,
        xp_prox=200,
        dima=5,
        amet=1,
        streak=0,
        feitas_hoje=0,
        especies=0,
        total_especies=18,
    )
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
