from pathlib import Path
from typing import Callable


def deploy_by_writing(
    content: str,
    description: str,
    destination: Path,
) -> Callable[[], Path]:
    def deploy() -> Path:
        print(f"Writing {description} to {destination}")
        with open(destination, "w") as destination_file:
            destination_file.write(
                content,
            )
        return destination

    return deploy
