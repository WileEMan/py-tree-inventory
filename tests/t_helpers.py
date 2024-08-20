import logging
import os
import sys
from io import StringIO
from pathlib import Path
from typing import Union

from tree_inventory import main

PathOrStr = Union[Path, str]


def write_text_to_file(fname: PathOrStr, new_text: str):
    """Simply writes text into a file, overwriting the file."""
    dir = Path(fname).parent
    if not dir.exists():
        dir.mkdir(parents=True)
    with open(str(fname), "wt") as fh:
        fh.write(new_text)


def main_with_log(args, raise_on_error: bool = True) -> str:
    """Run main(), but capture everything that it outputs
    to the console into the returned string.
    """

    string_stream = StringIO()
    handler1 = logging.StreamHandler(string_stream)
    handler2 = logging.StreamHandler(stream=sys.stdout)
    handler1.setLevel(logging.INFO)
    handler2.setLevel(logging.INFO)
    root_logger = logging.getLogger()
    root_logger.addHandler(handler1)
    root_logger.addHandler(handler2)
    # for hh in root_logger.handlers:
    # print(f"Handler: {hh}")
    all_loggers = [logging.getLogger(name) for name in logging.root.manager.loggerDict]
    for lg in all_loggers:
        lg.setLevel(logging.DEBUG)
    try:
        main(args)
        handler1.flush()
        handler2.flush()
        ret_str = string_stream.getvalue()
        if raise_on_error and "Error" in ret_str:
            raise RuntimeError(
                f"An error was observed when calling main.  Arguments were:\nmain([{args}])\nFull log follows: -------\n"
                + ret_str
            )
        return ret_str
    finally:
        root_logger.removeHandler(handler1)
        root_logger.removeHandler(handler2)


def samepath(A: Path, B: Path):
    """Similar to os.path.samefile(), but does not require that the files actually exist
    or be the same on disk.  This checks only that the paths would refer to the same
    file."""
    A_str = os.path.normcase(os.path.normpath(A.resolve()))
    B_str = os.path.normcase(os.path.normpath(B.resolve()))
    return A_str == B_str


def parse_results(text: str, base_A: Path, base_B: Path):
    """Parse results of a comparison operation.  Tailored to the
    text format of --compare.
    """

    file_mismatches = []
    missing_A = []
    missing_B = []

    # Maintain 'current_A', a stack of the paths that have been listed.  Each entry in
    # current_A is a tuple where the first entry is the indent for a path and the second
    # is that absolute path itself.
    current_A = [(0, base_A)]

    lines = text.split("\n")
    for iLine in range(len(lines)):
        line = lines[iLine]
        if line.lstrip().startswith("A:"):
            iA = line.index("A:")
            current_A = [(0, Path(line[iA + 2 :].lstrip()))]
        if "vs" in line:
            iA = line.index("(A)")
            info = ""
            try:
                new_A = line[0:iA].strip()
                new_indent = len(line[0:iA].rstrip()) - len(line[0:iA].strip())
                info += f"line: {line}\n"
                info += f"A substring: {line[0:iA]}\n"
                info += f"new_indent = {new_indent}\n"
                info += f"current_A before = {current_A}\n"
                hypothetical_A = current_A[-1][1] / Path(new_A)
                if new_indent != current_A[-1][0] or not samepath(current_A[-1][1], hypothetical_A):
                    while new_indent <= current_A[-1][0]:
                        info += f"last entry has indent {current_A[-1][0]} so moving up.\n"
                        current_A = current_A[:-1]
                    info += f"current_A now = {current_A}\n"
                    current_A.append((new_indent, current_A[-1][1] / Path(new_A)))
            except Exception as ex:
                raise RuntimeError(
                    f"With line:\n{line}\nA substring: {new_A}\nbase_A: {base_A}\n{info}" + str(ex)
                ) from ex
        if "Files within this folder mismatch" in line:
            file_mismatches.append(str(current_A[-1][1].relative_to(base_A)))
        if "absent from A" in line:
            i_apos1 = line.index("'")
            i_apos2 = line.rindex("'")
            absent = line[i_apos1 + 1 : i_apos2]
            missing_A.append(absent)
        if "absent from B" in line:
            i_apos1 = line.index("'")
            i_apos2 = line.rindex("'")
            absent = line[i_apos1 + 1 : i_apos2]
            missing_B.append(absent)

    return file_mismatches, missing_A, missing_B
