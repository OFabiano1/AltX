# isso aq desenha o card png do >player.
# so pillow, fonte padrao (abre ate offline, sem baixar nada).
# qualquer falha levanta PlayerCardError e o cog segue so com o texto.

import unicodedata
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont


# ─── erro ───


class PlayerCardError(Exception):
    """nao deu pra montar o card."""


# ─── cores (as mesmas do visual.py) ───

BASE = (14, 17, 22)
BORDA = (42, 52, 64)
TEXTO = (232, 237, 242)
TEXTO_APAGADO = (138, 151, 166)
VIOLETA = (143, 0, 255)
VIOLETA_CLARO = (186, 108, 255)
VERDE = (74, 222, 128)

LARGURA = 900
MARGEM = 36


def _seguro(texto: str) -> str:
    """sem acento: a fonte padrao so tem ascii."""
    return (
        unicodedata.normalize("NFKD", texto or "")
        .encode("ascii", "ignore")
        .decode("ascii")
    )


def render_player(
    nome: str,
    nivel: int,
    xp: int,
    xp_prox: int,
    n_conq: int,
    total_conq: int,
    destaques: list[str],
    moedas: str = "",
) -> bytes:
    """card do player. destaques: ate 3 linhas. moedas: ex "10 dima - 5 amet"."""
    try:
        altura = 340 + max(0, len(destaques[:3])) * 44 + (40 if moedas else 0)
        img = Image.new("RGB", (LARGURA, altura), BASE)
        desenho = ImageDraw.Draw(img)
        desenho.rounded_rectangle(
            [4, 4, LARGURA - 4, altura - 4], 24, outline=BORDA, width=2
        )
        f_nome = ImageFont.load_default(size=52)
        f_nivel = ImageFont.load_default(size=32)
        f_num = ImageFont.load_default(size=40)
        f_linha = ImageFont.load_default(size=28)
        f_rodape = ImageFont.load_default(size=20)

        # avatar: circulo com a inicial.
        cx, cy, raio = MARGEM + 60, MARGEM + 60, 60
        desenho.ellipse(
            [cx - raio, cy - raio, cx + raio, cy + raio], fill=VIOLETA
        )
        inicial = _seguro(nome.strip()[:1]).upper() or "?"
        f_inicial = ImageFont.load_default(size=64)
        comp = desenho.textlength(inicial, font=f_inicial)
        desenho.text(
            (cx - comp / 2, cy - 44), inicial, font=f_inicial, fill=TEXTO
        )

        desenho.text(
            (MARGEM + 150, MARGEM + 8),
            _seguro(nome)[:20],
            font=f_nome,
            fill=TEXTO,
        )
        desenho.text(
            (MARGEM + 150, MARGEM + 72),
            f"NIVEL {nivel}",
            font=f_nivel,
            fill=VIOLETA_CLARO,
        )

        # barra de xp.
        y = MARGEM + 150
        fracao = max(0.0, min(1.0, xp / max(1, xp_prox)))
        desenho.rounded_rectangle(
            [MARGEM, y, LARGURA - MARGEM, y + 24], 12, fill=BORDA
        )
        cheio = int((LARGURA - MARGEM * 2) * fracao)
        if cheio > 0:
            desenho.rounded_rectangle(
                [MARGEM, y, MARGEM + cheio, y + 24], 12, fill=VIOLETA
            )
        y += 38
        desenho.text(
            (MARGEM, y), f"{xp}/{xp_prox} xp", font=f_linha, fill=TEXTO_APAGADO
        )
        y += 44

        # numeros.
        desenho.text(
            (MARGEM, y),
            f"{n_conq}/{total_conq} conquistas",
            font=f_num,
            fill=TEXTO,
        )
        y += 56
        if moedas:
            desenho.text(
                (MARGEM, y),
                _seguro(moedas)[:48],
                font=f_linha,
                fill=TEXTO_APAGADO,
            )
            y += 40
        for d in destaques[:3]:
            desenho.text(
                (MARGEM, y), f"* {_seguro(d)[:40]}", font=f_linha, fill=VERDE
            )
            y += 44

        rodape = "Player to Player - Axolotl BR"
        comp = desenho.textlength(rodape, font=f_rodape)
        desenho.text(
            (LARGURA - MARGEM - comp, altura - 40),
            rodape,
            font=f_rodape,
            fill=TEXTO_APAGADO,
        )
        saida = BytesIO()
        img.save(saida, format="PNG")
        return saida.getvalue()
    except PlayerCardError:
        raise
    except Exception as e:
        raise PlayerCardError(f"render quebrou: {e}") from e
