# exibicao da conquista de halloween: catalogo fixo + linha pronta pro embed.
# roda com: pytest tests/test_conquista.py (na raiz do bot).

from cogs.halloween import CONQUISTAS, linha_conquista


def test_conquista_halloween_2026_existe():
    info = CONQUISTAS["halloween2026"]
    assert (info["icone"], info["nome"]) == ("🎃", "Halloween 2026")
    assert "31/10/2026" in info["desc"]


def test_linha_conquista():
    assert linha_conquista([("halloween2026", "31/10/2026")]) == [
        "🎃 **Halloween 2026** — 31/10/2026"
    ]
    assert linha_conquista([("halloween2026", "")]) == ["🎃 **Halloween 2026**"]
