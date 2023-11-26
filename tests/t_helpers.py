import sys
import logging
from io import StringIO
from typing import Union
from pathlib import Path

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


def parse_results(text: str, base_A: Path, base_B: Path):
    """Parse results of a comparison operation.  Tailored to the
    text format of --compare.
    """

    file_mismatches = []
    missing_A = []
    missing_B = []

    lines = text.split("\n")
    current_A = None
    # current_B = None
    for iLine in range(len(lines)):
        line = lines[iLine]
        if line.lstrip().startswith("A:"):
            iA = line.index("A:")
            current_A = Path(line[iA + 2 :].lstrip()).relative_to(base_A)
        # if line.lstrip().startswith("B:"):
        # iB = line.index("B:")
        # current_B = Path(line[iB + 2 :].lstrip()).relative_to(base_B)
        if "vs" in line:
            iA = line.index("(A)")
            # iVS = line.index("vs")
            # iB = line.index("(B)")
            current_A = Path(line[0:iA].strip()).relative_to(base_A)
            # current_B = Path(line[iVS + 2 : iB].strip()).relative_to(base_B)
        if "Files within this folder mismatch" in line:
            file_mismatches.append(str(current_A))
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
