from os import mkdir
from pathlib import Path
from typing import Callable


def deploy_by_creating_directory(
    destination: Path,
) -> Callable[[], Path]:
    def deploy() -> Path:
        if not destination.exists():
            print(f"Creating directory at {destination}")
            mkdir(destination)
        return destination

    return deploy
