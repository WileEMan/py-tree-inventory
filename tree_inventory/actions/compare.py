import logging
from pathlib import Path
from typing import Union

from .helpers import find_checksum_file, read_checksum_file, extract_record

logger = logging.getLogger(__name__)

PathOrStr = Union[Path, str]


def compare_trees(A: Path, B: Path):
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
    A_rel_path, A_subrecord = extract_record(A_record, A_record_file, A)
    B_rel_path, B_subrecord = extract_record(B_record, B_record_file, B)

    if A_rel_path != B_rel_path:
        raise RuntimeError(
            f"After locating the subdirectory of interest in trees A and B, the relative paths do not match:"
            + f"\n\tRelative path A: {A_rel_path}"
            + f"\n\tRelative path B: {B_rel_path}"
        )

    def compare_branch(A_base_path: tuple, B_base_path: tuple, A_record: dict, B_record: dict, level: int):
        """compare_branch() is the recursive workhorse of compare_trees() that operates on a particular
        folder within the trees.  The 'level' argument in some parts of this code increments with each
        level deeper into the tree, but here is only starts incrementing once a directory with
        differences is found.  That way, we can keep track of how many folders we've displayed information
        for and only show a couple of levels of differences.

        Note: if changing the aesthetics here (the text written to msg), also check that test_general.py's
        parse_results() function is updated to be able to parse the new output.
        """

        if A_record["MD5"] == B_record["MD5"] and A_record["n_files"] == B_record["n_files"]:
            return ""
        if level >= 3:
            return ""

        is_diff = False
        msg = ""
        if A_record["MD5-files_only"] != B_record["MD5-files_only"]:
            msg += ("\t" * (level + 1)) + f"Files within this folder mismatch.\n"
            is_diff = True

        # Check if any subdirectories are absent first

        A_subdirectories = A_record["subdirectories"] if "subdirectories" in A_record else {}
        B_subdirectories = B_record["subdirectories"] if "subdirectories" in B_record else {}
        for name in A_subdirectories:
            a_record = A_subdirectories[name]
            if name not in B_subdirectories:
                msg += ("\t" * (level + 1)) + f"Directory '{name}' absent from B.\n"
                is_diff = True
        for name in B_subdirectories:
            b_record = B_subdirectories[name]
            if name not in A_subdirectories:
                msg += ("\t" * (level + 1)) + f"Directory '{name}' absent from A.\n"
                is_diff = True

        # Once we find the levels where there are differences, we always want to
        # start incrementing the level.
        if level > 0 or is_diff:
            level += 1

        for name in set(A_subdirectories.keys()).intersection(B_subdirectories.keys()):
            a_record = A_subdirectories[name]
            b_record = B_subdirectories[name]
            msg += compare_branch(A_base_path / name, B_base_path / name, a_record, b_record, level)

        if len(msg) > 0:
            msg = ("\t" * (level - 1)) + f"{A_base_path} (A) vs {B_base_path} (B):\n" + msg

        return msg

    A_base_path = A_record_file.parent / A_rel_path
    B_base_path = B_record_file.parent / B_rel_path
    result = compare_branch(A_base_path, B_base_path, A_subrecord, B_subrecord, 0)
    if not (result):
        result = "\tNo differences found.\n"
    result = f"\n\nAs of {A_record['calculated_at']} (A) and {B_record['calculated_at']} (B):\n" + result
    logger.info(result)
