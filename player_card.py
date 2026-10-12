# isso aq desenha o card png do >player.
# so pillow + stdlib (abre ate offline, sem baixar nada).
# camadas sobre dark (nunca preto chapado), violeta de destaque.
# qualquer falha levanta PlayerCardError e o cog segue so com o texto.

import unicodedata
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont


# ─── erro ───


class PlayerCardError(Exception):
    """nao deu pra montar o card."""


# ─── cores (as mesmas do visual.py) ───

BASE = (14, 17, 22)
FUNDO_BAIXO = (26, 17, 40)
SUPERFICIE = (21, 26, 33)
BORDA = (42, 52, 64)
TEXTO = (232, 237, 242)
TEXTO_APAGADO = (138, 151, 166)
VIOLETA = (143, 0, 255)
VIOLETA_CLARO = (186, 108, 255)
CIANO = (34, 211, 238)
ROXO = (192, 132, 252)
LARANJA = (251, 146, 60)

LARGURA = 1000
MARGEM = 40


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
    pos: int | None,
    xp: int,
    xp_prox: int,
    dima: int,
    amet: int,
    doces: int,
    streak: int,
    feitas_hoje: int,
    especies: int,
    total_especies: int,
) -> bytes:
    """card do player: nivel, xp, moedas e grade streak/diarias/especies/rank."""
    try:
        altura = 580
        img = Image.new("RGB", (LARGURA, altura), BASE)
        desenho = ImageDraw.Draw(img)

        # fundo em degrade: base em cima, violeta soturno embaixo.
        for y in range(altura):
            t = y / max(1, altura - 1)
            desenho.line(
                [(0, y), (LARGURA, y)],
                fill=tuple(int(BASE[i] + (FUNDO_BAIXO[i] - BASE[i]) * t) for i in range(3)),
            )
        desenho.rounded_rectangle(
            [4, 4, LARGURA - 4, altura - 4], 28, outline=BORDA, width=2
        )

        f_titulo = ImageFont.load_default(size=44)
        f_num = ImageFont.load_default(size=38)
        f_rotulo = ImageFont.load_default(size=24)
        f_linha = ImageFont.load_default(size=28)
        f_rodape = ImageFont.load_default(size=20)

        y = MARGEM
        nivel_txt = f"NIVEL {nivel}"
        if pos:
            nivel_txt += f"  -  #{pos}"
        desenho.text((MARGEM, y), nivel_txt, font=f_titulo, fill=VIOLETA_CLARO)
        y += 62

        # barra de xp com %.
        fracao = max(0.0, min(1.0, xp / max(1, xp_prox)))
        desenho.rounded_rectangle([MARGEM, y, LARGURA - MARGEM, y + 26], 13, fill=BORDA)
        cheio = int((LARGURA - MARGEM * 2) * fracao)
        if cheio > 0:
            desenho.rounded_rectangle([MARGEM, y, MARGEM + cheio, y + 26], 13, fill=VIOLETA)
        y += 34
        desenho.text(
            (MARGEM, y),
            f"{xp}/{xp_prox} xp  -  {int(fracao * 100)}%",
            font=f_linha,
            fill=TEXTO_APAGADO,
        )
        y += 48

        # moedas: icone + numero.
        x = MARGEM
        f_moeda = ImageFont.load_default(size=32)
        for desenha, cor, valor in (
            (_losango, CIANO, dima),
            (_coracao, ROXO, amet),
            (_doce, LARANJA, doces),
        ):
            desenha(desenho, x + 14, y + 16, 14, cor)
            x += 36
            texto = str(valor)
            desenho.text((x, y), texto, font=f_moeda, fill=TEXTO)
            x += desenho.textlength(texto, font=f_moeda) + 44
        y += 58

        # grade 2x2.
        cel_w = (LARGURA - MARGEM * 2 - 24) // 2
        cel_h = 92
        celulas = [
            ("streak", f"{streak} dias"),
            ("diarias hoje", f"{feitas_hoje}/3"),
            ("especies", f"{especies}/{total_especies}"),
            ("rank", f"#{pos}" if pos else "-"),
        ]
        for i, (rotulo, valor) in enumerate(celulas):
            gx = MARGEM + (i % 2) * (cel_w + 24)
            gy = y + (i // 2) * (cel_h + 16)
            desenho.rounded_rectangle([gx, gy, gx + cel_w, gy + cel_h], 18, fill=SUPERFICIE)
            desenho.rounded_rectangle([gx, gy, gx + cel_w, gy + cel_h], 18, outline=BORDA, width=1)
            desenho.text((gx + 20, gy + 10), rotulo.upper(), font=f_rotulo, fill=TEXTO_APAGADO)
            desenho.text((gx + 20, gy + 36), valor, font=f_num, fill=TEXTO)

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
