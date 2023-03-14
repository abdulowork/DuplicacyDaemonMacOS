#!/usr/bin/python3
from __future__ import annotations

import gzip
import logging
import os
import selectors
import shlex
import shutil
import subprocess
import typing
from dataclasses import dataclass
from logging import Logger
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from selectors import PollSelector
from typing import Union, List, Callable, Optional
from urllib.request import urlopen
import itertools


@dataclass
class Env:
    name: str

    def get(self) -> Optional[str]:
        return os.environ.get(self.name)

    def get_unwrapped(self) -> str:
        return os.environ[self.name]


duplicacy_path_env = Env("DUPLICACY_PATH")
prune_keep_arguments_env = Env("PRUNE_KEEP_ARGUMENTS")
prune_keep_arguments = prune_keep_arguments_env.get()

healthcheck_backup_url_env = Env("HEALTHCHECK_BACKUP_URL")
healthcheck_prune_url_env = Env("HEALTHCHECK_PRUNE_URL")
healthcheck_check_url_env = Env("HEALTHCHECK_CHECK_URL")
healthcheck_connection_timeout = 60

log_path_env = Env("LOG_PATH")

skip_display_alert_env = Env("SKIP_DISPLAY_ALERT")
skip_check_for_full_disk_access_env = Env("SKIP_CHECK_FOR_FULL_DISK_ACCESS")


def main() -> None:
    logger: Logger
    log_path = Path(log_path_env.get_unwrapped()).joinpath("duplicacy.log")
    try:
        logger = create_rotating_logger(log_path=log_path)
    except Exception as exception:
        print("Couldn't create a logger")
        print(exception)
        show_alert(
            f"Couldn't create a logger. Aborting backup. See logs in {str(log_path.parent)}"
        )
        exit(1)

    commands = Commands(
        logger=logger,
        log_path=log_path,
    )
    commands.check_for_full_disk_access()
    commands.run_backup()
    commands.run_prune()
    commands.run_check()

    return None


@dataclass
class Commands:
    logger: Logger
    log_path: Path

    def check_for_full_disk_access(self) -> None:
        if skip_check_for_full_disk_access_env.get() is not None:
            self.logger.info("Skipping full disk access check")
            return

        try:
            os.listdir("/Library/Application Support/com.apple.TCC")
        except PermissionError as exception:
            self.logger.error(f"Full disk access permission error: {exception}")
            show_alert(
                f"Backup process probably doesn't have Full Disk Access. Grant Full Disk Access to backup_exec or disable this check with --skip-check-for-full-disk-access",
            )
            exit(1)
        except Exception as exception:
            self.logger.error(f"Check for full disk access failed: {exception}")
            show_alert(
                f"Check for full disk access failed. Aborting backup. See logs in {str(self.log_path.parent)}",
            )
            exit(1)

    def run_backup(self) -> None:
        self.__run_subprocess_safely(
            args=[duplicacy_path_env.get_unwrapped(), "backup", "-stats"],
            on_start=lambda: show_alert("Beginning backup", timeout=3),
            subprocess_events_handler=self.__subprocess_event_handler(
                action="Backup",
                url_to_ping=healthcheck_backup_url_env.get(),
            ),
        )

    def run_prune(self) -> None:
        if prune_keep_arguments is None:
            self.logger.info("Skipping prune")
            return

        self.__run_subprocess_safely(
            args=[duplicacy_path_env.get_unwrapped(), "prune"]
            + flatten(
                [["-keep", interval] for interval in shlex.split(prune_keep_arguments)]
            ),
            on_start=lambda: None,
            subprocess_events_handler=self.__subprocess_event_handler(
                action="Prune",
                url_to_ping=healthcheck_prune_url_env.get(),
            ),
        )

    def run_check(self) -> None:
        self.__run_subprocess_safely(
            args=[duplicacy_path_env.get_unwrapped(), "check"],
            on_start=lambda: None,
            subprocess_events_handler=self.__subprocess_event_handler(
                action="Check",
                url_to_ping=healthcheck_check_url_env.get(),
            ),
        )

    def __subprocess_event_handler(
        self,
        action: str,
        url_to_ping: Optional[str],
    ) -> SubprocessEventsHandler:
        return SubprocessEventsHandler(
            action=action,
            url_to_ping=url_to_ping,
            log_path=self.log_path,
            logger=self.logger,
        )

    def __run_subprocess_safely(
        self,
        args: List[str],
        on_start: Callable[[], None],
        subprocess_events_handler: SubprocessEventsHandler,
    ) -> None:
        try:
            on_start()
            subprocess_exit_code = self.__run_subprocess(args=args)
            if subprocess_exit_code != 0:
                subprocess_events_handler.on_non_zero_exit_code(subprocess_exit_code)
            else:
                subprocess_events_handler.on_zero_exit_code()
        except Exception as exception:
            subprocess_events_handler.on_generic_failure(exception)

    def __run_subprocess(self, args: List[str]) -> int:
        self.logger.info(f"Running subprocess: {args}")

        process = subprocess.Popen(
            args=args,
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
        )

        selector = PollSelector()
        selector.register(process.stdout, selectors.EVENT_READ)  # type: ignore
        selector.register(process.stderr, selectors.EVENT_READ)  # type: ignore

        while len(selector.get_map()) != 0:
            ready = selector.select()
            for key, events in ready:
                bytes_line = key.fileobj.readline()  # type: ignore
                if len(bytes_line) == 0:
                    selector.unregister(key.fileobj)
                    continue

                log: Union[bytes, str]
                try:
                    log = bytes_line.decode()
                except Exception as e:
                    self.logger.error(e)
                    log = bytes_line

                if key.fileobj == process.stdout:
                    self.logger.info(log)
                if key.fileobj == process.stderr:
                    self.logger.error(log)

        process.wait()

        return process.returncode


@dataclass
class SubprocessEventsHandler:
    action: str
    url_to_ping: Optional[str]
    log_path: Path
    logger: Logger

    def on_generic_failure(self, exception: Exception) -> None:
        self.logger.error(f"Error in {self.action}: {exception}")
        self.__report_to_healthcheck(
            result=JobGenericFailure(),
        )
        show_alert(
            f"Something went wrong during {self.action}. See logs in {str(self.log_path)}"
        )

    def on_non_zero_exit_code(self, exit_code: int) -> None:
        message = f"{self.action} failed with exit code: {exit_code}"
        self.logger.error(message)
        self.__report_to_healthcheck(
            result=JobFailureWithCode(exit_code=exit_code),
        )
        show_alert(f"{message}. See logs in {str(self.log_path)}")

    def on_zero_exit_code(self) -> None:
        message = f"{self.action} was successful"
        self.logger.info(message)
        self.__report_to_healthcheck(
            result=JobSuccess(),
        )
        show_alert(message)

    def __report_to_healthcheck(
        self,
        result: Union[JobSuccess, JobGenericFailure, JobFailureWithCode],
    ) -> None:
        if self.url_to_ping is None:
            self.logger.info(f"Skipping healthcheck ping for {self.action}")
            return

        if isinstance(result, JobSuccess):
            pass
        elif isinstance(result, JobGenericFailure):
            self.url_to_ping += "/fail"
        elif isinstance(result, JobFailureWithCode):
            self.url_to_ping += f"/{result.exit_code}"

        urlopen(self.url_to_ping, timeout=healthcheck_connection_timeout)


@dataclass
class JobSuccess:
    pass


@dataclass
class JobGenericFailure:
    pass


@dataclass
class JobFailureWithCode:
    exit_code: int


def show_alert(
    message: str,
    timeout: int = 60,
) -> None:
    if skip_display_alert_env.get() is not None:
        return
    try:
        subprocess.run(
            args=[
                "osascript",
                "-e",
                f'display alert "Backup service" message "{message}"',
            ],
            timeout=timeout,
        )
    except TimeoutError as timeout:
        # This is ok
        pass
    except Exception as e:
        print(f"Alert error: {e}")


def create_rotating_logger(log_path: Path) -> Logger:
    logger = logging.getLogger()
    rotating_file_handler = TimedRotatingFileHandler(
        filename=log_path,
        when="D",
        interval=1,
        backupCount=7,
    )
    rotating_file_handler.setFormatter(
        logging.Formatter(
            fmt="[%(asctime)s] %(levelname)s [%(name)s.%(funcName)s:%(lineno)d] %(message)s",
            datefmt="%d/%b/%Y %H:%M:%S",
        )
    )

    def namer(name: str) -> str:
        return name + "log.gz"

    rotating_file_handler.namer = namer

    def rotator(source: str, dest: str) -> None:
        with open(source, "rb") as f_in:
            with gzip.open(dest, "wb") as f_out:
                shutil.copyfileobj(f_in, f_out)
        os.remove(source)

    rotating_file_handler.rotator = rotator
    logger.addHandler(rotating_file_handler)
    logger.setLevel(logging.DEBUG)
    return logger


T = typing.TypeVar("T")


def flatten(list_of_lists: List[List[T]]) -> List[T]:
    return list(itertools.chain.from_iterable(list_of_lists))


if __name__ == "__main__":
    main()
