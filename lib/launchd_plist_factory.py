import plistlib
from pathlib import Path
from typing import Optional, List

from lib.start_calendar_interval import StartCalendarInterval


class LaunchdPlistFactory:
    def __init__(
        self,
        service_identifier: str,
        backup_script_path: Path,
        backup_binary_deployment_path: Path,
        duplicacy_path: Path,
        repository_path: Path,
        logging_directory: Path,
        healthcheck_url: Optional[str],
        calendar_intervals: List[StartCalendarInterval],
        skip_check_for_full_disk_access: bool,
        skip_display_alert: bool,
    ):
        self.__service_identifier = service_identifier
        self.__backup_script_path = backup_script_path
        self.__backup_binary_deployment_path = backup_binary_deployment_path
        self.__duplicacy_path = duplicacy_path
        self.__repository_path = repository_path
        self.__logging_directory = logging_directory
        self.__healthcheck_url = healthcheck_url
        self.__calendar_intervals = calendar_intervals
        self.__skip_check_for_full_disk_access = skip_check_for_full_disk_access
        self.__skip_display_alert = skip_display_alert

    def plist_string(self) -> str:
        environment_variables = dict()
        if self.__healthcheck_url is not None:
            environment_variables["HEALTHCHECK_URL"] = self.__healthcheck_url
        if self.__skip_check_for_full_disk_access:
            environment_variables["SKIP_CHECK_FOR_FULL_DISK_ACCESS"] = "1"
        if self.__skip_display_alert:
            environment_variables["SKIP_DISPLAY_ALERT"] = "1"

        environment_variables["BACKUP_SCRIPT_PATH"] = str(self.__backup_script_path)
        environment_variables["LOG_PATH"] = str(self.__logging_directory)
        environment_variables["DUPLICACY_PATH"] = str(self.__duplicacy_path)

        intervals = list()
        for interval in self.__calendar_intervals:
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
            "Label": self.__service_identifier,
            "Program": str(self.__backup_binary_deployment_path),
            "EnvironmentVariables": environment_variables,
            "WorkingDirectory": str(self.__repository_path),
            "StartCalendarInterval": intervals,
            "StandardOutPath": str(
                self.__logging_directory.joinpath("backup.stdout.log")
            ),
            "StandardErrorPath": str(
                self.__logging_directory.joinpath("backup.stderr.log")
            ),
        }

        return plistlib.dumps(launchd_plist).decode()
