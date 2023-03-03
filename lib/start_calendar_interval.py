from __future__ import annotations

import csv
from dataclasses import dataclass
from typing import Optional, Any


class StartCalendarIntervalException(Exception):
    pass


@dataclass
class StartCalendarInterval:
    minute: Optional[int]
    hour: Optional[int]
    day: Optional[int]
    weekday: Optional[int]
    month: Optional[int]

    @staticmethod
    def from_csv(value: str) -> StartCalendarInterval:
        interval = next(csv.reader([value]))
        if len(interval) != 5:
            print(
                f"Incorrect value specified for StartCalendarInterval: {value}. See --help for format details"
            )
            raise StartCalendarIntervalException()

        return StartCalendarInterval(
            minute=StartCalendarInterval.convert(interval[0], range(0, 60), "minute"),
            hour=StartCalendarInterval.convert(interval[1], range(0, 24), "hour"),
            day=StartCalendarInterval.convert(interval[2], range(1, 32), "day"),
            weekday=StartCalendarInterval.convert(interval[3], range(0, 7), "weekday"),
            month=StartCalendarInterval.convert(interval[4], range(1, 13), "month"),
        )

    @staticmethod
    def convert(value: str, valid_range: range, title: str) -> Optional[int]:
        if is_empty(value):
            return None

        integer = int(value)
        if integer not in valid_range:
            print(f"Incorrect value for {title}, must be in range {valid_range}")
            raise StartCalendarIntervalException()
        return integer


def is_empty(value: Any) -> bool:
    return len(value) == 0
