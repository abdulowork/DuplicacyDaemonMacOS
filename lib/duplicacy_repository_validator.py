from pathlib import Path


class DuplicacyRepositoryValidator:
    def validate(self, specified_path: Path) -> None:
        expected_directory_name = ".duplicacy"
        expected_directory_path = specified_path.joinpath(expected_directory_name)
        if not expected_directory_path.exists():
            print(
                f"Warning: couldn't find {expected_directory_name} in {expected_directory_path.parent}"
            )
