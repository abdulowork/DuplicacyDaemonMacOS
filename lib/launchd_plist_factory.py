import plistlib
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List

from lib.start_calendar_interval import StartCalendarInterval
import run_backup


@dataclass
class LaunchdPlistFactory:
    service_identifier: str
    backup_script_path: Path
    backup_binary_deployment_path: Path
    duplicacy_path: Path
    repository_path: Path
    logging_directory: Path
    healthcheck_backup_url: Optional[str]
    healthcheck_prune_url: Optional[str]
    healthcheck_check_url: Optional[str]
    prune_keep_arguments: List[str]
    calendar_intervals: List[StartCalendarInterval]
    skip_check_for_full_disk_access: bool
    skip_display_alert: bool

    def plist_string(self) -> str:
        environment_variables = dict()
        if self.healthcheck_backup_url is not None:
            environment_variables[
                run_backup.healthcheck_backup_url_env.name
            ] = self.healthcheck_backup_url
        if self.healthcheck_prune_url is not None:
            environment_variables[
                run_backup.healthcheck_prune_url_env.name
            ] = self.healthcheck_prune_url
        if self.healthcheck_check_url is not None:
            environment_variables[
                run_backup.healthcheck_check_url_env.name
            ] = self.healthcheck_check_url
        if len(self.prune_keep_arguments) > 0:
            environment_variables[run_backup.prune_keep_arguments_env.name] = " ".join(
                self.prune_keep_arguments
            )
        if self.skip_check_for_full_disk_access:
            environment_variables[
                run_backup.skip_check_for_full_disk_access_env.name
            ] = "1"
        if self.skip_display_alert:
            environment_variables[run_backup.skip_display_alert_env.name] = "1"

        environment_variables["BACKUP_SCRIPT_PATH"] = str(self.backup_script_path)
        environment_variables[run_backup.log_path_env.name] = str(
            self.logging_directory
        )
        environment_variables[run_backup.duplicacy_path_env.name] = str(
            self.duplicacy_path
        )

        intervals = list()
        for interval in self.calendar_intervals:
            output = dict()
            if interval.minute is not None:
                output["Minute"] = interval.minute
            if interval.hour is not None:
                output["Hour"] = interval.hour
            if interval.day is not None:
                output["Day"] = interval.day
            if interval.weekday is not None:
                output["Weekday"] = interval.weekday
            if interval.month is not None:
                output["Month"] = interval.month
            intervals.append(output)

        launchd_plist = {
            "Label": self.service_identifier,
            "Program": str(self.backup_binary_deployment_path),
            "EnvironmentVariables": environment_variables,
            "WorkingDirectory": str(self.repository_path),
            "StartCalendarInterval": intervals,
            "StandardOutPath": str(
                self.logging_directory.joinpath("backup.stdout.log")
            ),
            "StandardErrorPath": str(
                self.logging_directory.joinpath("backup.stderr.log")
            ),
        }

        return plistlib.dumps(launchd_plist).decode()
