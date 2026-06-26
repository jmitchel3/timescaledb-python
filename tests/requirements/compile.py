#!/usr/bin/env python
from __future__ import annotations

import os
import subprocess
import sys
from functools import partial
from pathlib import Path

if __name__ == "__main__":
    os.chdir(Path(__file__).parent)
    common_args = [
        "uv",
        "pip",
        "compile",
        "--quiet",
        "--generate-hashes",
        "--constraint",
        "-",
        "requirements.in",
        *sys.argv[1:],
    ]
    run = partial(subprocess.run, check=True)

    # Generate requirements for each supported Python version
    for py_version in ["3.11", "3.12", "3.13", "3.14"]:
        run(
            [
                *common_args,
                "--python",
                py_version,
                "--output-file",
                f"py{py_version.replace('.', '')}.txt",
            ],
            input=b"",  # No Django constraint needed
        )
