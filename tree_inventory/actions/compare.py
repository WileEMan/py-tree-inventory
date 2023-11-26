import logging
from pathlib import Path
from typing import Union

from .helpers import find_checksum_file, read_checksum_file, extract_record

logger = logging.getLogger(__name__)

PathOrStr = Union[Path, str]


def compare_trees(A: Path, B: Path, depth: int = 2):
    """compare_trees() implements the main record comparison facility
    of tree_inventory and is invoked via the --compare command-line
    option.  It relies entirely on the records for comparison, so
    calculate must be called before comparing and the comparison will
    only be as up-to-date as the records.  The output should display
    a "as-of" timestamp.  Only differences should be highlighted, and
    with only enough detail to home in on the areas of interest.  The
    compare_trees() function is basically a "diff" operation, but based
    on the checksum record files.
    """

    logger.info(f"Comparing trees:\n\tA: {A}\n\tB: {B}")
    A_record_file = find_checksum_file(A)
    B_record_file = find_checksum_file(B)
    logger.debug(f"Checksum file A found at: {A_record_file}")
    logger.debug(f"Checksum file B found at: {B_record_file}")
    A_record = read_checksum_file(A_record_file)
    B_record = read_checksum_file(B_record_file)
    A_rel_path, A_records = extract_record(A_record, A_record_file, A)
    B_rel_path, B_records = extract_record(B_record, B_record_file, B)
    A_subrecord = A_records[-1]
    B_subrecord = B_records[-1]

    if A_rel_path != B_rel_path:
        raise RuntimeError(
            f"After locating the subdirectory of interest in trees A and B, the relative paths do not match:"
            + f"\n\tRelative path A: {A_rel_path}"
            + f"\n\tRelative path B: {B_rel_path}"
        )

    def compare_branch(A_base_path: tuple, B_base_path: tuple, A_record: dict, B_record: dict, level: int):
        """compare_branch() is the recursive workhorse of compare_trees() that operates on a particular
        folder within the trees.

        Note: if changing the aesthetics here (the text written to msg), also check that test_general.py's
        parse_results() function is updated to be able to parse the new output.
        """

        # tab = "o"      # For debugging.
        tab = "\t"

        if "MD5" not in A_record:
            return (tab * (level)) + f"{A_base_path} (A) does not have a checksum.  Run --calculate first.\n"
        if "MD5" not in B_record:
            return (tab * (level)) + f"{B_base_path} (B) does not have a checksum.  Run --calculate first.\n"

        if A_record["MD5"] == B_record["MD5"] and A_record["n_files"] == B_record["n_files"]:
            return ""

        msg = ""
        if A_record["MD5-files_only"] != B_record["MD5-files_only"]:
            msg += (tab * (level + 1)) + f"Files within this folder mismatch.\n"

        # Check if any subdirectories are absent first

        A_subdirectories = A_record["subdirectories"] if "subdirectories" in A_record else {}
        B_subdirectories = B_record["subdirectories"] if "subdirectories" in B_record else {}
        for name in A_subdirectories:
            a_record = A_subdirectories[name]
            if name not in B_subdirectories:
                msg += (tab * (level + 1)) + f"Directory '{name}' absent from B.\n"
        for name in B_subdirectories:
            b_record = B_subdirectories[name]
            if name not in A_subdirectories:
                msg += (tab * (level + 1)) + f"Directory '{name}' absent from A.\n"

        for name in set(A_subdirectories.keys()).intersection(B_subdirectories.keys()):
            a_record = A_subdirectories[name]
            b_record = B_subdirectories[name]
            if level + 1 < depth:
                msg += compare_branch(A_base_path / name, B_base_path / name, a_record, b_record, level + 1)
            else:
                if a_record["MD5"] != b_record["MD5"]:
                    msg += (tab * (level + 1)) + f"Directory '{name}' contains differences between A and B.\n"

        msg = (tab * (level)) + f"{A_base_path} (A) vs {B_base_path} (B):\n" + msg

        # msg += f"Considered: {A_base_path} (A {A_record['MD5']}) vs {B_base_path} (B {B_record['MD5']})\n"

        return msg

    A_base_path = A_record_file.parent / A_rel_path
    B_base_path = B_record_file.parent / B_rel_path
    result = compare_branch(A_base_path, B_base_path, A_subrecord, B_subrecord, level=0)
    if not (result):
        result = "\tNo differences found.\n"
    result = f"\n\nAs of {A_record['calculated_at']} (A) and {B_record['calculated_at']} (B):\n" + result
    logger.info(result)
