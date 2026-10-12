# isso aq desenha o card png do >player.
# so pillow + stdlib (abre ate offline: sem avatar vira inicial).
# camadas sobre dark (nunca preto chapado), violeta de destaque.
# qualquer falha levanta PlayerCardError e o cog segue so com o texto.

import unicodedata
import urllib.request
from io import BytesIO
from pathlib import Path

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
VERDE = (74, 222, 128)
CIANO = (34, 211, 238)
ROXO = (192, 132, 252)
LARANJA = (251, 146, 60)

LARGURA = 1000
MARGEM = 40
HEADERS = {"User-Agent": "ALT-bot/1.0 (+discord)"}


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


# ─── avatar ───


def _pasta_avatar() -> Path:
    pasta = Path(__file__).parent / "data" / "player_avatars"
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta


def _avatar(url: str | None, user_id: int, tamanho: int) -> Image.Image | None:
    """avatar redondo do discord. None se nao baixar/abrir."""
    if not url:
        return None
    destino = _pasta_avatar() / f"{user_id}.png"
    try:
        if not (destino.exists() and destino.stat().st_size > 0):
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=8) as resp:
                dados = resp.read()
            if not dados:
                return None
            destino.write_bytes(dados)
        with Image.open(destino) as img:
            img = img.convert("RGBA").resize((tamanho, tamanho), Image.LANCZOS)
            mascara = Image.new("L", (tamanho, tamanho), 0)
            ImageDraw.Draw(mascara).ellipse([0, 0, tamanho, tamanho], fill=255)
            saida = Image.new("RGBA", (tamanho, tamanho), (0, 0, 0, 0))
            saida.paste(img, (0, 0), mascara)
            return saida
    except Exception:
        return None


# ─── card ───


def render_player(perfil: dict) -> bytes:
    """card do player. perfil: {user_id, nome, avatar_url, nivel, pos, xp,
    xp_prox, n_conq, total_conq, recentes[nomes], dima, amet, doces,
    streak, feitas_hoje, especies, total_especies}."""
    try:
        recentes = (perfil.get("recentes") or [])[:3]
        altura = 620 + len(recentes) * 42
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

        f_nome = ImageFont.load_default(size=54)
        f_titulo = ImageFont.load_default(size=40)
        f_num = ImageFont.load_default(size=38)
        f_rotulo = ImageFont.load_default(size=24)
        f_linha = ImageFont.load_default(size=28)
        f_rodape = ImageFont.load_default(size=20)

        # cabecalho: avatar com anel + nome + nivel/rank.
        tam = 120
        cx, cy = MARGEM + tam // 2, MARGEM + tam // 2
        desenho.ellipse(
            [cx - tam // 2 - 5, cy - tam // 2 - 5, cx + tam // 2 + 5, cy + tam // 2 + 5],
            fill=VIOLETA,
        )
        foto = _avatar(perfil.get("avatar_url"), perfil.get("user_id", 0), tam)
        if foto is not None:
            img.paste(foto, (cx - tam // 2, cy - tam // 2), foto)
        else:
            desenho.ellipse(
                [cx - tam // 2, cy - tam // 2, cx + tam // 2, cy + tam // 2],
                fill=SUPERFICIE,
            )
            inicial = _seguro((perfil.get("nome") or "?")[:1]).upper() or "?"
            f_ini = ImageFont.load_default(size=64)
            comp = desenho.textlength(inicial, font=f_ini)
            desenho.text((cx - comp / 2, cy - 44), inicial, font=f_ini, fill=TEXTO)

        desenho.text(
            (MARGEM + tam + 24, MARGEM + 8),
            _seguro(perfil.get("nome") or "?")[:20],
            font=f_nome,
            fill=TEXTO,
        )
        nivel_txt = f"NIVEL {perfil.get('nivel', 1)}"
        if perfil.get("pos"):
            nivel_txt += f"  -  #{perfil['pos']}"
        desenho.text(
            (MARGEM + tam + 24, MARGEM + 74),
            nivel_txt,
            font=f_titulo,
            fill=VIOLETA_CLARO,
        )

        # barra de xp com %.
        y = MARGEM + tam + 28
        xp, xp_prox = perfil.get("xp", 0), max(1, perfil.get("xp_prox", 1))
        fracao = max(0.0, min(1.0, xp / xp_prox))
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

        # moedas com icone.
        x = MARGEM
        f_moeda = ImageFont.load_default(size=32)
        for desenha, cor, valor in (
            (_losango, CIANO, perfil.get("dima", 0)),
            (_coracao, ROXO, perfil.get("amet", 0)),
            (_doce, LARANJA, perfil.get("doces", 0)),
        ):
            desenha(desenho, x + 14, y + 16, 14, cor)
            x += 36
            texto = str(valor)
            desenho.text((x, y), texto, font=f_moeda, fill=TEXTO)
            x += desenho.textlength(texto, font=f_moeda) + 44
        y += 58

        # grade 2x2: conquistas, streak, diarias, especies.
        cel_w = (LARGURA - MARGEM * 2 - 24) // 2
        cel_h = 92
        celulas = [
            ("conquistas", f"{perfil.get('n_conq', 0)}/{perfil.get('total_conq', 0)}"),
            ("streak", f"{perfil.get('streak', 0)} dias"),
            ("diarias hoje", f"{perfil.get('feitas_hoje', 0)}/3"),
            ("especies", f"{perfil.get('especies', 0)}/{perfil.get('total_especies', 0)}"),
        ]
        for i, (rotulo, valor) in enumerate(celulas):
            gx = MARGEM + (i % 2) * (cel_w + 24)
            gy = y + (i // 2) * (cel_h + 16)
            desenho.rounded_rectangle([gx, gy, gx + cel_w, gy + cel_h], 18, fill=SUPERFICIE)
            desenho.rounded_rectangle([gx, gy, gx + cel_w, gy + cel_h], 18, outline=BORDA, width=1)
            desenho.text((gx + 20, gy + 10), rotulo.upper(), font=f_rotulo, fill=TEXTO_APAGADO)
            desenho.text((gx + 20, gy + 36), valor, font=f_num, fill=TEXTO)
        y += cel_h * 2 + 16 + 28

        # novidades.
        if recentes:
            desenho.text((MARGEM, y), "NOVIDADES", font=f_rotulo, fill=TEXTO_APAGADO)
            y += 32
            for d in recentes:
                desenho.text(
                    (MARGEM, y), f"* {_seguro(d)[:42]}", font=f_linha, fill=VERDE
                )
                y += 42

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
