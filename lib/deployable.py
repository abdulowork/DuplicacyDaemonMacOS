from dataclasses import dataclass
from pathlib import Path
from typing import Callable


@dataclass
class Deployable:
    deploy: Callable[[], Path]
    user: str
    group: str
    mode: int
