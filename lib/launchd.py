import subprocess
from pathlib import Path


class Launchd:
    def __init__(self, launchctl_path: Path):
        self.__launchctl_path = launchctl_path

    def bootout_if_needed(
        self,
        service_identifier: str,
    ) -> None:
        service_target = f"system/{service_identifier}"

        if (
            subprocess.run(
                args=[self.__launchctl_path, "print", service_target],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            ).returncode
            == 0
        ):
            print(f"Booting out {service_target}")
            subprocess.run(
                args=[self.__launchctl_path, "bootout", service_target],
            )
        else:
            print(
                f"Service target {service_target} hasn't been found, skipping bootout"
            )

    def bootstrap(
        self,
        service_plist_deployment_path: Path,
    ) -> None:
        print(f"Boostrapping launchd service at {str(service_plist_deployment_path)}")
        subprocess.run(
            args=[
                self.__launchctl_path,
                "bootstrap",
                "system",
                service_plist_deployment_path,
            ],
        )
