# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
"""
Console used by all processes. We are forcing colors and terminal output as Breeze is supposed
to be only run in CI or real development terminal - in both cases we want to have colors on.
"""

from __future__ import annotations

import os
from enum import Enum
from typing import NamedTuple, TextIO

from rich.console import Console
from rich.theme import Theme

from airflow_breeze.utils.functools_cache import clearable_cache

recording_width = os.environ.get("RECORD_BREEZE_WIDTH")
recording_file = os.environ.get("RECORD_BREEZE_OUTPUT_FILE")


def get_theme() -> Theme:
    try:
        from airflow_breeze.utils.cache import read_from_cache_file

        if read_from_cache_file("suppress_colour") is not None:
            return Theme(
                {
                    "success": "bold italic",
                    "info": "bold",
                    "warning": "italic",
                    "error": "italic underline",
                    "special": "bold italic underline",
                }
            )
    except ImportError:
        # sometimes we might want to use console before the cache folder is determined
        # and in this case we will get an import error due to partial initialization.
        # in this case we switch to default theme
        pass
    return Theme(
        {
            "success": "green",
            "info": "bright_blue",
            "warning": "bright_yellow",
            "error": "red",
            "special": "magenta",
        }
    )


class MessageType(Enum):
    SUCCESS = "success"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    SPECIAL = "special"


def message_type_from_return_code(return_code: int) -> MessageType:
    if return_code == 0:
        return MessageType.SUCCESS
    return MessageType.ERROR


class Output(NamedTuple):
    title: str
    file_name: str

    @property
    def file(self) -> TextIO:
        return open(self.file_name, "a+")

    @property
    def escaped_title(self) -> str:
        return self.title.replace("[", "\\[")


CONSOLE_WIDTH: int | None = int(os.environ.get("CI_WIDTH", "202")) if os.environ.get("CI") else None


@clearable_cache
def get_console(output: Output | None = None) -> Console:
    return Console(
        force_terminal=True,
        color_system="standard",
        width=CONSOLE_WIDTH if not recording_width else int(recording_width),
        file=output.file if output else None,
        theme=get_theme(),
        record=True if recording_file else False,
    )


@clearable_cache
def get_stderr_console(output: Output | None = None) -> Console:
    return Console(
        force_terminal=True,
        color_system="standard",
        stderr=True,
        file=output.file if output else None,
        width=CONSOLE_WIDTH if not recording_width else int(recording_width),
        theme=get_theme(),
        record=True if recording_file else False,
    )


def console_print(*message) -> None:
    return get_console().print(*message)
