import shutil
import stat
from pathlib import Path
from typing import Optional


class DuplicacyExecutableFinderException(Exception):
    pass


class DuplicacyExecutableFinder:
    def __init__(
        self,
        expected_owner: str,
        expected_group: str,
    ):
        self.__expected_owner = expected_owner
        self.__expected_group = expected_group

    def find(
        self,
        specified_path: Optional[Path],
    ) -> Path:
        duplicacy_path: Path
        if specified_path is not None:
            duplicacy_path = specified_path
            print(f"Using supplied duplicacy path: {specified_path}")
        else:
            found_path = shutil.which("duplicacy")
            if found_path is not None:
                print(f"Using duplicacy found in PATH: {found_path}")
                duplicacy_path = Path(found_path)
            else:
                print(f"Couldn't find duplicacy executable")
                raise DuplicacyExecutableFinderException()

        self.__validate_duplicacy_path(
            path=duplicacy_path,
        )

        return duplicacy_path

    def __validate_duplicacy_path(self, path: Path) -> None:
        if not path.exists():
            print(f"Warning: Couldn't find duplicacy executable at path: {path}")
            raise DuplicacyExecutableFinderException()
        self.__check_ownership(path=path)

        flags = path.stat().st_mode
        if not (flags & stat.S_IXUSR):
            print(f"Warning: {path} is not executable")

        parent_directory = path.parent
        self.__check_ownership(path=parent_directory)

    def __check_ownership(
        self,
        path: Path,
    ) -> None:
        if not (
            path.owner() == self.__expected_owner
            and path.group() == self.__expected_group
        ):
            print(
                f"Warning: {path} owned by {path.owner()}:{path.group()} instead of {self.__expected_owner}:{self.__expected_group}"
            )
        if path.stat().st_mode & stat.S_IWOTH:
            print(f"Warning: {path} is writable by others")
