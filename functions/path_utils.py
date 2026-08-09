from pathlib import Path

from dotenv import load_dotenv


def get_project_root() -> Path:
    current_file = Path(__file__).resolve()
    if current_file.parent.name.lower() == "functions":
        return current_file.parent.parent
    return current_file.parent


def get_data_dir() -> Path:
    return get_project_root() / "5MinutesData"


def load_project_env() -> Path:
    project_root = get_project_root()
    load_dotenv(project_root / ".env")
    return project_root
