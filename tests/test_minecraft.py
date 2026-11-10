# ─── minecraft ───

# parser das texturas da sessionserver (formato real da mojang) e
# validacao de nick. a chamada de rede de verdade fica no fim, pulavel.

import base64
import json
import os

import pytest

from cogs import minecraft as mc


def _sessao(texturas: dict) -> dict:
    valor = base64.b64encode(json.dumps({"textures": texturas}).encode()).decode()
    return {"id": "853c80ef3c3749fdaa49938b674adae6", "properties": [{"name": "textures", "value": valor}]}


def test_skin_classica_com_capa():
    p = mc.parse_texturas(
        _sessao(
            {
                "SKIN": {"url": "http://textures.minecraft.net/texture/abc"},
                "CAPE": {"url": "http://textures.minecraft.net/texture/def"},
            }
        )
    )
    assert p == {
        "skin_url": "https://textures.minecraft.net/texture/abc",
        "modelo": "classico",
        "capa_url": "https://textures.minecraft.net/texture/def",
    }


def test_skin_slim_sem_capa_e_perfil_sem_textura():
    p = mc.parse_texturas(
        _sessao({"SKIN": {"url": "http://t/x", "metadata": {"model": "slim"}}})
    )
    assert p["modelo"] == "slim" and p["capa_url"] is None
    vazio = mc.parse_texturas({})
    assert vazio == {"skin_url": None, "modelo": "classico", "capa_url": None}


def test_embeds_sem_ordem_solta_no_rodape():
    # o rodape do >minecraft dizia ">skin fulano mostra a skin inteira": tirado.
    p = {
        "nome": "jeb_",
        "uuid": "853c80ef3c3749fdaa49938b674adae6",
        "skin_url": "https://textures.minecraft.net/texture/abc",
        "modelo": "classico",
        "capa_url": None,
    }
    perfil = mc._embed_perfil(p)
    skin = mc._embed_skin(p)
    assert perfil.footer.text == skin.footer.text == mc.visual.FOOTER
    assert "baixar a skin" in skin.description and "capa" not in skin.description
    assert skin.image.url.endswith("?overlay&scale=10")


def test_uuid_com_hifen():
    assert (
        mc.uuid_com_hifen("853c80ef3c3749fdaa49938b674adae6")
        == "853c80ef-3c37-49fd-aa49-938b674adae6"
    )


def test_nick_valido():
    for ok in ("jeb_", "Notch", "a_b", "x" * 16):
        assert mc.NICK_VALIDO.match(ok)
    for ruim in ("", "ab", "x" * 17, "com espaco", "acentuação", "../../etc"):
        assert not mc.NICK_VALIDO.match(ruim)


@pytest.mark.skipif(os.getenv("ALT_SEM_REDE") == "1", reason="sem rede")
def test_perfil_real_do_jeb():
    try:
        p = mc.buscar_perfil("jeb_")
        sumido = mc.buscar_perfil("zzqqxxnaoexiste1")
    except mc.MinecraftAPIError:
        pytest.skip("mojang fora do ar")
    assert p["uuid"] == "853c80ef3c3749fdaa49938b674adae6"
    assert p["skin_url"].startswith("https://textures.minecraft.net/")
    assert p["capa_url"]
    assert sumido is None
