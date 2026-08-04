from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_windows_launcher_invokes_next_cli_with_node_directly() -> None:
    script = (REPO_ROOT / "scripts" / "run_local.ps1").read_text(encoding="utf-8")

    assert "next\\dist\\bin\\next" in script
    assert "& $Node $NextCli dev" in script
    assert "npm run dev" not in script


def test_next_development_origins_allow_both_local_names() -> None:
    config = (REPO_ROOT / "apps" / "web" / "next.config.ts").read_text(encoding="utf-8")

    assert 'allowedDevOrigins: ["localhost", "127.0.0.1"]' in config
