#!/usr/bin/python3

import gzip
import logging
import os
import selectors
import shutil
import subprocess
from dataclasses import dataclass
from logging import Logger
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from selectors import PollSelector
from typing import Union
from urllib.request import urlopen

duplicacy_path = os.environ["DUPLICACY_PATH"]

healthcheck_url = os.environ.get("HEALTHCHECK_URL")
healthcheck_connection_timeout = 60

log_path = Path(os.environ["LOG_PATH"]).joinpath("duplicacy.log")

skip_display_alert = os.environ.get("SKIP_DISPLAY_ALERT") is not None
skip_check_for_full_disk_access = (
    os.environ.get("SKIP_CHECK_FOR_FULL_DISK_ACCESS") is not None
)


def backup() -> None:
    logger: Logger
    try:
        logger = create_rotating_logger()
    except Exception as exception:
        print("Couldn't create a logger")
        print(exception)
        show_alert(
            f"Couldn't create a logger. Aborting backup. See logs in {str(log_path.parent)}"
        )
        exit(1)

    check_for_full_disk_access(logger=logger)

    try:
        show_alert("Beginning backup", timeout=3)

        backup_process = subprocess.Popen(
            args=[duplicacy_path, "backup", "-stats"],
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
        )

        selector = PollSelector()
        selector.register(backup_process.stdout, selectors.EVENT_READ)  # type: ignore
        selector.register(backup_process.stderr, selectors.EVENT_READ)  # type: ignore

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
                    logger.error(e)
                    log = bytes_line

                if key.fileobj == backup_process.stdout:
                    logger.info(log)
                if key.fileobj == backup_process.stderr:
                    logger.error(log)

        backup_process.wait()

        if backup_process.returncode != 0:
            backup_failed_message = (
                f"Backup failed with exit code: {backup_process.returncode}"
            )
            logger.error(backup_failed_message)
            report_to_healthcheck(
                result=JobFailureWithCode(exit_code=backup_process.returncode),
                logger=logger,
            )
            show_alert(f"{backup_failed_message}. See logs in {str(log_path)}")
        else:
            message = "Backup was successful"
            logger.info(message)
            report_to_healthcheck(
                result=JobSuccess(),
                logger=logger,
            )
            show_alert(message)
    except Exception as exception:
        logger.error(f"Error while backing up: {exception}")
        report_to_healthcheck(
            result=JobGenericFailure(),
            logger=logger,
        )
        show_alert(f"Something went wrong during backup. See logs in {str(log_path)}")


@dataclass
class JobSuccess:
    pass


@dataclass
class JobGenericFailure:
    pass


@dataclass
class JobFailureWithCode:
    exit_code: int


def check_for_full_disk_access(
    logger: Logger,
) -> None:
    if skip_check_for_full_disk_access:
        logger.info("Skipping full disk access check")
        return

    try:
        os.listdir("/Library/Application Support/com.apple.TCC")
    except PermissionError as exception:
        logger.error(f"Full disk access permission error: {exception}")
        show_alert(
            f"Backup process probably doesn't have Full Disk Access. Grant Full Disk Access to backup_exec or disable this check with --skip-check-for-full-disk-access",
        )
        exit(1)
    except Exception as exception:
        logger.error(f"Check for full disk access failed: {exception}")
        show_alert(
            f"Check for full disk access failed. Aborting backup. See logs in {str(log_path.parent)}",
        )
        exit(1)


def report_to_healthcheck(
    result: Union[JobSuccess, JobGenericFailure, JobFailureWithCode], logger: Logger
) -> None:
    if healthcheck_url is None:
        logger.info("URL for healthcheck is not specified, skipping")
        return

    url_to_ping = healthcheck_url
    if isinstance(result, JobSuccess):
        pass
    elif isinstance(result, JobGenericFailure):
        url_to_ping += "/fail"
    elif isinstance(result, JobFailureWithCode):
        url_to_ping += f"/{result.exit_code}"

    urlopen(url_to_ping, timeout=healthcheck_connection_timeout)


def show_alert(
    message: str,
    timeout: int = 60,
) -> None:
    if skip_display_alert:
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


def namer(name: str) -> str:
    return name + "log.gz"


def rotator(source: str, dest: str) -> None:
    with open(source, "rb") as f_in:
        with gzip.open(dest, "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)
    os.remove(source)


def create_rotating_logger() -> Logger:
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
    rotating_file_handler.namer = namer
    rotating_file_handler.rotator = rotator
    logger.addHandler(rotating_file_handler)
    logger.setLevel(logging.DEBUG)
    return logger


if __name__ == "__main__":
    backup()
