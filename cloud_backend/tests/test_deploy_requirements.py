from pathlib import Path


def test_deploy_requirements_include_docx_runtime() -> None:
    requirements_path = Path(__file__).resolve().parents[1] / "requirements.deploy.txt"
    packages = {
        line.split("[", 1)[0].split("<", 1)[0].split(">", 1)[0].split("=", 1)[0].strip().lower()
        for line in requirements_path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }

    assert "python-docx" in packages
