# ─── slash sync ───

# o guild_id do deploy era o id do emoji :02:, o sync dava 403 e o
# slash ficou meses com 29 comandos velhos. isso trava a escolha certa.

import main

SERVIDOR = 994118849731506306
EMOJI = "1028808570466213918"


def test_guild_id_valido_ganha():
    assert main.escolher_servidor(str(SERVIDOR), [SERVIDOR, 1]) == SERVIDOR


def test_id_errado_cai_no_unico_servidor():
    assert main.escolher_servidor(EMOJI, [SERVIDOR]) == SERVIDOR
    assert main.escolher_servidor(None, [SERVIDOR]) == SERVIDOR
    assert main.escolher_servidor(" lixo ", [SERVIDOR]) == SERVIDOR


def test_varios_servidores_sem_id_valido_vai_global():
    assert main.escolher_servidor(EMOJI, [SERVIDOR, 1]) is None
    assert main.escolher_servidor(None, []) is None
