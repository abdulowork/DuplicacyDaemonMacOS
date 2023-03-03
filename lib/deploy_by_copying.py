from pathlib import Path
from shutil import copyfile
from typing import Callable


def deploy_by_copying(
    source: Path,
    destination: Path,
) -> Callable[[], Path]:
    def deploy() -> Path:
        print(f"Copying from {source} to {destination}")
        copyfile(
            src=source,
            dst=destination,
        )
        return destination

    return deploy
