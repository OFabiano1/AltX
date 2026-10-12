# isso aq desenha o card png do >player.
# so pillow, fonte padrao (abre ate offline, sem baixar nada).
# moedas com icone desenhado (losango, coracao, doce), sem avatar e sem nome.
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
CIANO = (34, 211, 238)
ROXO = (192, 132, 252)
LARANJA = (251, 146, 60)

LARGURA = 900
MARGEM = 36


def _seguro(texto: str) -> str:
    """sem acento: a fonte padrao so tem ascii."""
    return (
        unicodedata.normalize("NFKD", texto or "")
        .encode("ascii", "ignore")
        .decode("ascii")
    )


# ─── icones desenhados ───


def _losango(desenho: ImageDraw.ImageDraw, x: int, y: int, r: int, cor: tuple) -> None:
    """dima: losango ciano."""
    desenho.polygon([(x, y - r), (x + r, y), (x, y + r), (x - r, y)], fill=cor)


def _coracao(desenho: ImageDraw.ImageDraw, x: int, y: int, r: int, cor: tuple) -> None:
    """ametista: coracao roxo (2 bolas + triangulo)."""
    desenho.ellipse([x - r, y - r, x, y + r // 2], fill=cor)
    desenho.ellipse([x, y - r, x + r, y + r // 2], fill=cor)
    desenho.polygon([(x - r, y), (x + r, y), (x, y + r)], fill=cor)


def _doce(desenho: ImageDraw.ImageDraw, x: int, y: int, r: int, cor: tuple) -> None:
    """doces: bala laranja (bola + pontas)."""
    desenho.polygon(
        [(x - r + 2, y - 5), (x - r - 9, y - 11), (x - r - 9, y + 11)], fill=cor
    )
    desenho.polygon(
        [(x + r - 2, y - 5), (x + r + 9, y - 11), (x + r + 9, y + 11)], fill=cor
    )
    desenho.ellipse([x - r, y - r, x + r, y + r], fill=cor)


def render_player(
    nivel: int,
    xp: int,
    xp_prox: int,
    n_conq: int,
    total_conq: int,
    destaques: list[str],
    dima: int,
    amet: int,
    doces: int,
) -> bytes:
    """card do player. destaques: ate 3 linhas (ex conquistas novas)."""
    try:
        altura = 360 + max(0, len(destaques[:3])) * 44
        img = Image.new("RGB", (LARGURA, altura), BASE)
        desenho = ImageDraw.Draw(img)
        desenho.rounded_rectangle(
            [4, 4, LARGURA - 4, altura - 4], 24, outline=BORDA, width=2
        )
        f_nivel = ImageFont.load_default(size=44)
        f_num = ImageFont.load_default(size=40)
        f_linha = ImageFont.load_default(size=28)
        f_moeda = ImageFont.load_default(size=30)
        f_rodape = ImageFont.load_default(size=20)

        y = MARGEM
        desenho.text((MARGEM, y), f"NIVEL {nivel}", font=f_nivel, fill=VIOLETA_CLARO)
        y += 62

        # barra de xp.
        fracao = max(0.0, min(1.0, xp / max(1, xp_prox)))
        desenho.rounded_rectangle(
            [MARGEM, y, LARGURA - MARGEM, y + 24], 12, fill=BORDA
        )
        cheio = int((LARGURA - MARGEM * 2) * fracao)
        if cheio > 0:
            desenho.rounded_rectangle(
                [MARGEM, y, MARGEM + cheio, y + 24], 12, fill=VIOLETA
            )
        y += 36
        desenho.text(
            (MARGEM, y), f"{xp}/{xp_prox} xp", font=f_linha, fill=TEXTO_APAGADO
        )
        y += 46

        # moedas: icone + numero.
        x = MARGEM
        for desenha, cor, valor in (
            (_losango, CIANO, dima),
            (_coracao, ROXO, amet),
            (_doce, LARANJA, doces),
        ):
            desenha(desenho, x + 13, y + 15, 13, cor)
            x += 34
            texto = str(valor)
            desenho.text((x, y), texto, font=f_moeda, fill=TEXTO)
            x += desenho.textlength(texto, font=f_moeda) + 40
        y += 52

        # conquistas.
        desenho.text(
            (MARGEM, y),
            f"{n_conq}/{total_conq} conquistas",
            font=f_num,
            fill=TEXTO,
        )
        y += 58
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
