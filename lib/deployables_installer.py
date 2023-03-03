from logging import Logger
from os import chmod
from shutil import chown
from typing import List

from lib.deployable import Deployable


class DeployablesInstaller:
    def deploy(self, deployables: List[Deployable]) -> None:
        for deployable in deployables:
            path = deployable.deploy()
            print(
                f"Setting {path} to be owned by {deployable.user}:{deployable.group} with mode {oct(deployable.mode)}"
            )
            chown(path=path, user=deployable.user, group=deployable.group)
            chmod(path=path, mode=deployable.mode)
