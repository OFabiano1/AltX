# banco isolado por teste: troca o caminho antes de criar o schema.
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

import data


@pytest.fixture
def banco(tmp_path, monkeypatch):
    monkeypatch.setattr(data, "DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr(data, "BACKUP_DIR", tmp_path / "backups")
    # sem isso o init importa o xp.json legado de verdade no banco vazio.
    monkeypatch.setattr(data, "LEGACY_XP", tmp_path / "nope.json")
    data.init()
    return data
