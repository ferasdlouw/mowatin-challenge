"""render.yaml guards: TestClient never runs uvicorn, so the start command is checked here."""

from __future__ import annotations

import re
from pathlib import Path

RENDER_YAML = Path(__file__).resolve().parents[3] / "render.yaml"


def _text() -> str:
    return RENDER_YAML.read_text(encoding="utf-8")


def test_uvicorn_access_log_is_off():
    """uvicorn's access log prints query strings, i.e. /v1/glossary?q=<user text>."""
    start = re.search(r"startCommand:\s*(.+)", _text())
    assert start
    assert "--no-access-log" in start.group(1)
    assert "--factory app.main:create_app" in start.group(1)


def test_production_settings_and_names_only():
    text = _text()
    assert re.search(r"key: ENV\s+value: production", text)
    assert "healthCheckPath: /health" in text
    # Render hides files outside rootDir, and the API needs data/.
    assert not re.search(r"^\s*rootDir:", text, re.MULTILINE)
    for name in ("ALLOWED_ORIGINS", "TRUSTED_PROXY_HOPS", "LLM_API_KEY", "JUDGE_API_KEY"):
        assert re.search(rf"key: {name}\s+sync: false", text), name


LOCK = RENDER_YAML.parent / "backend" / "requirements.lock"
REQUIREMENTS = RENDER_YAML.parent / "backend" / "requirements.txt"
_PIN = re.compile(r"^([A-Za-z0-9_.-]+)(?:\[[^\]]*\])?==([^\s;]+)", re.MULTILINE)


def _pins(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    return {name.lower().replace("_", "-"): version for name, version in _PIN.findall(text)}


def test_render_installs_every_package_from_the_hash_lock():
    # NEW-8: transitive dependencies were resolved at build time, unpinned and unhashed.
    build = re.search(r"buildCommand:\s*(.+)", _text())
    assert build
    assert build.group(1).strip() == "pip install --require-hashes -r backend/requirements.lock"


def test_lock_pins_and_hashes_every_package():
    blocks: list[list[str]] = []
    for line in LOCK.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line[0].isspace():
            blocks[-1].append(line)
        else:
            blocks.append([line])
    assert len(blocks) >= 15
    for block in blocks:
        assert "==" in block[0], block[0]
        assert any("--hash=sha256:" in line for line in block), block[0]


def test_lock_matches_the_direct_pins():
    # A bump in requirements.txt (e.g. Dependabot) fails here until the lock is regenerated
    # with the command at the top of requirements.lock.
    lock = _pins(LOCK)
    for name, version in _pins(REQUIREMENTS).items():
        assert lock.get(name) == version, name
