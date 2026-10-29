"""The YouTube test data must never reach main: youtube_test refuses any
.env.test that is not the dev-youtube-test branch or that points at main."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import youtube_test  # noqa: E402


def setup(tmp_path, monkeypatch, test_env: str, main_env="DATABASE_URL=postgresql://main-host/db\n"):
    (tmp_path / ".env").write_text(main_env, encoding="utf-8")
    (tmp_path / ".env.test").write_text(test_env, encoding="utf-8")
    monkeypatch.setattr(youtube_test, "ROOT", tmp_path)


def test_accepts_the_test_branch(tmp_path, monkeypatch):
    setup(tmp_path, monkeypatch,
          "DATABASE_URL=postgresql://test-host/db\nNEON_BRANCH=dev-youtube-test\n")
    assert youtube_test.test_database_url() == "postgresql://test-host/db"


@pytest.mark.parametrize("env", [
    "DATABASE_URL=postgresql://main-host/db\nNEON_BRANCH=dev-youtube-test\n",  # main's URL
    "DATABASE_URL=postgresql://test-host/db\nNEON_BRANCH=main\n",              # wrong branch
    "DATABASE_URL=postgresql://test-host/db\n",                                 # no branch
    "NEON_BRANCH=dev-youtube-test\n",                                           # no URL
])
def test_refuses_anything_else(tmp_path, monkeypatch, env):
    setup(tmp_path, monkeypatch, env)
    with pytest.raises(SystemExit):
        youtube_test.test_database_url()
