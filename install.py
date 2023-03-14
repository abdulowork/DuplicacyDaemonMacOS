#!/usr/bin/python3

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path
from time import sleep
from typing import List, Optional

from lib.deploy_by_copying import deploy_by_copying
from lib.deploy_by_creating_directory import deploy_by_creating_directory
from lib.deploy_by_writing import deploy_by_writing
from lib.deployable import Deployable
from lib.deployables_installer import DeployablesInstaller
from lib.deployement_path_resolver import DeploymentPathResolver
from lib.duplicacy_executable_finder import DuplicacyExecutableFinder
from lib.duplicacy_repository_validator import DuplicacyRepositoryValidator
from lib.launchd import Launchd
from lib.launchd_plist_factory import LaunchdPlistFactory
from lib.start_calendar_interval import StartCalendarInterval

service_identifier = "com.duplicacy_macos_daemon.backup"

repo_directory = Path(__file__).parent

backup_script_name = "run_backup.py"
backup_script_path = repo_directory.joinpath(backup_script_name)

backup_binary_name = "backup_exec"
backup_binary_path = repo_directory.joinpath(backup_binary_name)

logging_directory = Path(f"/Library/Logs/{service_identifier}")
daemons_directory = Path("/Library/LaunchDaemons")

service_plist_deployment_path = daemons_directory.joinpath(
    service_identifier + ".plist"
)
default_binary_deployment_path = Path(
    f"/Library/Application Support/{service_identifier}"
)

launchctl_path = Path("/bin/launchctl")


def install() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--repository-path",
        help="Path where the duplicacy repository is initialized",
        required=True,
    )
    parser.add_argument(
        "--duplicacy-path",
        help="Path to the duplicacy executable. Will be searched in PATH if unspecified",
    )
    parser.add_argument(
        "--prune-keep",
        help="-keep argument that will be passed to the prune command",
        action="extend",
        nargs="+",
        type=str,
        default=[],
    )
    parser.add_argument(
        "--backup-script-deployment-path",
        help="Path where the run_backup.py will be deployed",
        default=str(default_binary_deployment_path),
    )
    parser.add_argument(
        "--backup-exec-deployment-path",
        help="Path where the backup_exec will be deployed",
        default=str(default_binary_deployment_path),
    )
    parser.add_argument(
        "--start-calendar-interval",
        help="Schedule for the backup to run in the CSV format: '<Minute>,<Hour>,<Day>,<Weekday>,<Month>'. For example use '--start-calendar-interval ,1,,,' to run backup every day at 1:00. See StartCalendarInterval in 'man launchd.plist' for details",
        action="extend",
        nargs="+",
        type=str,
        default=[",1,,,"],
    )
    parser.add_argument(
        "--skip-display-alert",
        help="Don't display alerts",
        action="store_true",
    )
    parser.add_argument(
        "--skip-check-for-full-disk-access",
        help="Don't check for TCC permissions before running the backup",
        action="store_true",
    )
    parser.add_argument(
        "--healthcheck-backup-url",
        help="healthchecks.io URL to ping on backup completion",
    )
    parser.add_argument(
        "--healthcheck-prune-url",
        help="healthchecks.io URL to ping on prune completion",
    )
    parser.add_argument(
        "--healthcheck-check-url",
        help="healthchecks.io URL to ping on check completion",
    )
    args = parser.parse_args()

    root = "root"
    wheel = "wheel"

    supplied_duplicacy_path: Optional[Path] = None
    if args.duplicacy_path is not None:
        supplied_duplicacy_path = Path(args.duplicacy_path)

    duplicacy_path = DuplicacyExecutableFinder(
        expected_owner=root,
        expected_group=wheel,
    ).find(
        specified_path=supplied_duplicacy_path,
    )
    DuplicacyRepositoryValidator().validate(
        specified_path=Path(args.repository_path),
    )

    installer = DeployablesInstaller()
    installer.deploy(
        deployables=[
            Deployable(
                deploy=deploy_by_creating_directory(
                    destination=default_binary_deployment_path,
                ),
                user=root,
                group=wheel,
                mode=0o775,
            ),
        ]
    )

    deployment_path_resolver = DeploymentPathResolver()
    backup_script_deployment_path = deployment_path_resolver.resolve(
        path=Path(args.backup_script_deployment_path),
        default_name=service_identifier + "." + backup_script_name,
        resource_description="backup script",
    )
    backup_binary_deployment_path = deployment_path_resolver.resolve(
        path=Path(args.backup_exec_deployment_path),
        default_name=service_identifier + "." + backup_binary_name,
        resource_description="backup executable",
    )

    intervals = [
        StartCalendarInterval.from_csv(interval)
        for interval in args.start_calendar_interval
    ]
    print_intervals(intervals=intervals)

    installer.deploy(
        deployables=[
            Deployable(
                deploy=deploy_by_writing(
                    content=LaunchdPlistFactory(
                        service_identifier=service_identifier,
                        backup_script_path=backup_script_deployment_path,
                        backup_binary_deployment_path=backup_binary_deployment_path,
                        duplicacy_path=duplicacy_path,
                        repository_path=Path(args.repository_path),
                        logging_directory=logging_directory,
                        healthcheck_backup_url=args.healthcheck_backup_url,
                        healthcheck_prune_url=args.healthcheck_prune_url,
                        healthcheck_check_url=args.healthcheck_check_url,
                        prune_keep_arguments=args.prune_keep,
                        calendar_intervals=intervals,
                        skip_display_alert=args.skip_display_alert,
                        skip_check_for_full_disk_access=args.skip_check_for_full_disk_access,
                    ).plist_string(),
                    description="service plist",
                    destination=service_plist_deployment_path,
                ),
                user=root,
                group=wheel,
                mode=0o600,
            ),
            Deployable(
                deploy=deploy_by_copying(
                    source=backup_script_path,
                    destination=backup_script_deployment_path,
                ),
                user=root,
                group=wheel,
                mode=0o700,
            ),
            Deployable(
                deploy=deploy_by_copying(
                    source=backup_binary_path,
                    destination=backup_binary_deployment_path,
                ),
                user=root,
                group=wheel,
                mode=0o700,
            ),
            Deployable(
                deploy=deploy_by_creating_directory(
                    destination=logging_directory,
                ),
                user=root,
                group=wheel,
                mode=0o755,
            ),
        ]
    )

    launchd = Launchd(
        launchctl_path=launchctl_path,
    )
    launchd.bootout_if_needed(
        service_identifier=service_identifier,
    )
    launchd.bootstrap(
        service_plist_deployment_path=service_plist_deployment_path,
    )

    if not args.skip_check_for_full_disk_access:
        print(
            f"\n!!! Don't forget to grant Full Disk Access to binary at {str(backup_binary_deployment_path)}"
        )
        print("\nSystem Preferences and the binary deployment path will open now")
        sleep(2)
        subprocess.run(
            args=[
                "/usr/bin/open",
                "x-apple.systempreferences:com.apple.preference.security?Privacy_AllFiles",
            ]
        )
        subprocess.run(args=["/usr/bin/open", "-R", backup_binary_deployment_path])

    print(
        f"\nTry:\n\n sudo launchctl kickstart system/{service_identifier}\n\nto begin backup\n"
    )
    print(f'Logs can be found in:\n\n open -R "{logging_directory}"\n')


def print_intervals(intervals: List[StartCalendarInterval]) -> None:
    print("\nLaunchd service will run at:")
    for interval in intervals:
        print(f"  {interval}")
    print()


if __name__ == "__main__":
    install()
