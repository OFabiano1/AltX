# isso aq desenha o card png da abertura de caixa.
# so pillow, fonte padrao (sem baixar nada, abre ate offline).
# qualquer falha levanta CaixaCardError e o cog segue so com o texto.

import unicodedata
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont


# ─── erro ───


class CaixaCardError(Exception):
    """nao deu pra montar o card."""


# ─── cores (as mesmas do visual.py) ───

BASE = (14, 17, 22)
BORDA = (42, 52, 64)
TEXTO = (232, 237, 242)
TEXTO_APAGADO = (138, 151, 166)

COR_RAR = {
    "comum": (138, 151, 166),
    "incomum": (82, 214, 168),
    "raro": (108, 182, 255),
    "épico": (143, 0, 255),
    "lendário": (251, 191, 36),
}

LARGURA = 900
MARGEM = 36


def _seguro(texto: str) -> str:
    """sem acento e sem simbolo: a fonte padrao so tem ascii."""
    base = (
        unicodedata.normalize("NFKD", texto or "")
        .encode("ascii", "ignore")
        .decode("ascii")
    )
    return base.replace("•", "-")


def render_caixa(titulo: str, linhas: list[tuple[str, str, int]]) -> bytes:
    """card da abertura. linhas: [(nome, rar, qtd)]. retorna os bytes."""
    try:
        altura = 170 + len(linhas) * 96 + 60
        img = Image.new("RGB", (LARGURA, altura), BASE)
        desenho = ImageDraw.Draw(img)
        desenho.rounded_rectangle(
            [4, 4, LARGURA - 4, altura - 4], 24, outline=BORDA, width=2
        )
        f_titulo = ImageFont.load_default(size=44)
        f_nome = ImageFont.load_default(size=36)
        f_detalhe = ImageFont.load_default(size=28)

        desenho.text((MARGEM, MARGEM), _seguro(titulo)[:32], font=f_titulo, fill=TEXTO)

        y = 130
        for nome, rar, qtd in linhas:
            cor = COR_RAR.get(rar, TEXTO_APAGADO)
            # barra lateral da raridade
            desenho.rounded_rectangle([MARGEM, y, MARGEM + 10, y + 72], 5, fill=cor)
            desenho.text(
                (MARGEM + 26, y + 2), _seguro(nome)[:22], font=f_nome, fill=TEXTO
            )
            detalhe = f"{rar} - {qtd}x"
            if qtd <= 1:
                detalhe += " - NOVO!"
            desenho.text(
                (MARGEM + 26, y + 44), _seguro(detalhe), font=f_detalhe, fill=cor
            )
            y += 96

        rodape = "Player to Player - Axolotl BR"
        f_rodape = ImageFont.load_default(size=20)
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
    except CaixaCardError:
        raise
    except Exception as e:
        raise CaixaCardError(f"render quebrou: {e}") from e
