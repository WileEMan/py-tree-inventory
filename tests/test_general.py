from time import sleep
import sys
import json
import shutil
import logging
from io import StringIO
from typing import Union, Optional
from pathlib import Path

from tree_inventory import main

logger = logging.getLogger(__name__)
PathOrStr = Union[Path, str]


def print_file(fname: PathOrStr, pretty_json: Optional[bool] = None):
    """Diagnostic helper- print out the contents of a file."""
    fname = Path(fname)
    if pretty_json is None:
        pretty_json = fname.suffix.lower() == ".json"
    print(f"Contents of file: {fname} {'[json] ' if pretty_json else ''}----")
    with open(str(fname), "rt") as fh:
        if pretty_json:
            print(json.dumps(json.load(fh), indent=4))
        else:
            print(fh.read())
    print(f"--------")


def write_text_to_file(fname: PathOrStr, new_text: str):
    """Simply writes text into a file, overwriting the file."""
    with open(str(fname), "wt") as fh:
        fh.write(new_text)


def main_with_log(args) -> str:
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
    try:
        main(args)
        handler1.flush()
        handler2.flush()
        return string_stream.getvalue()
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
    current_B = None
    for iLine in range(len(lines)):
        line = lines[iLine]
        if line.lstrip().startswith("A:"):
            iA = line.index("A:")
            current_A = Path(line[iA + 2 :].lstrip()).relative_to(base_A)
        if line.lstrip().startswith("B:"):
            iB = line.index("B:")
            current_B = Path(line[iB + 2 :].lstrip()).relative_to(base_B)
        if "vs" in line:
            iA = line.index("(A)")
            iVS = line.index("vs")
            iB = line.index("(B)")
            current_A = Path(line[0:iA].strip()).relative_to(base_A)
            current_B = Path(line[iVS + 2 : iB].strip()).relative_to(base_B)
        if "Files within this folder mismatch" in line:
            file_mismatches.append((current_A, current_B))

    return file_mismatches, missing_A, missing_B


def test_example():
    addn_options = ["--v", "--detail-files"]

    this_dir = Path(__file__).parent
    resources_path = this_dir / "resources"
    temp_path = this_dir / "temp"
    if temp_path.exists():
        shutil.rmtree(temp_path)
    try:
        shutil.copytree(resources_path, temp_path)
        sleep(1)

        ###
        ### With identical trees
        ###

        main_with_log(["--calculate", str(resources_path)] + addn_options)
        main_with_log(["--calculate", str(temp_path)] + addn_options)

        """
        test = main_with_log(["--compare", str(resources_path), str(temp_path)] + addn_options)
        assert "No differences" in test
        main_with_log(["--compare",
              str(resources_path / "Folder_C" / "Folder_C2"),
              str(temp_path / "Folder_C" / "Folder_C2")] + addn_options)
        assert "No differences" in test
        """

        ###
        ### Add file in Folder_C
        ###

        write_text_to_file(temp_path / "Folder_C" / "Created_File_1.txt", "I was created for this test.")
        main_with_log(["--calculate", str(temp_path)] + addn_options)
        print_file(resources_path / "tree_checksum.json")
        print_file(temp_path / "tree_checksum.json")
        test = main_with_log(["--compare", str(resources_path), str(temp_path)] + addn_options)
        file_mismatches, missing_A, missing_B = parse_results(test, resources_path, temp_path)
        print(f"File mismatches:\n{file_mismatches}")
        # assert "No differences" in test
        # main_with_log(["--compare",
        # str(resources_path / "Folder_C" / "Folder_C2"),
        # str(temp_path / "Folder_C" / "Folder_C2")] + addn_options)
        # assert "No differences" in test

    finally:
        shutil.rmtree(temp_path)


if __name__ == "__main__":
    test_example()
