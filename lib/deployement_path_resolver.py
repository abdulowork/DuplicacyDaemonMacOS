from pathlib import Path


class DeploymentPathResolverException(Exception):
    pass


class DeploymentPathResolver:
    def resolve(
        self,
        path: Path,
        default_name: str,
        resource_description: str,
    ) -> Path:
        if path.is_dir():
            return path.joinpath(default_name)
        if path.parent.is_dir():
            return path
        print(f"Warning: can't deploy {resource_description} to {path}")
        raise DeploymentPathResolverException()
