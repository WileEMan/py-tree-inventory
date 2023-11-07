import os
import sys
import argparse
import hashlib
import json
import logging
from tqdm import tqdm
from pathlib import Path
from datetime import datetime
from typing import Union

from .helpers import calculate_md5, enumerate_dir, find_checksum_file, read_checksum_file, extract_record

logger = logging.getLogger(__name__)

PathOrStr = Union[Path, str]


def calculate_tree(root: Path, detail_files: bool = False):
    """calculate_tree() implements the main record calculation facility
    of tree_inventory and is invoked via the --calculate command-line
    option.
    """

    logger.info(f"Calculating checksum for path '{root}'...")
    with tqdm(total=1) as progress:
        total_files = 0
        files_done = 0

        def calculate_branch(dir: Path, collection: dict, level: int):
            nonlocal progress, total_files, files_done
            checksum = hashlib.md5()
            files, subdirectories = enumerate_dir(dir)
            n_files = len(files)
            total_files += len(files)

            for name in subdirectories:
                checksum.update(name.encode("utf-8"))
                subcollection: dict = {}
                subdir_checksum, subdir_n_files, fileMD5, file_listing = calculate_branch(
                    dir / name, subcollection, level + 1
                )
                collection[name] = {
                    "n_files": n_files,
                    "subdirectories": subcollection,
                    "MD5": subdir_checksum.hexdigest(),
                    "MD5-files_only": fileMD5.hexdigest(),
                }
                if detail_files:
                    collection[name]["file-listing"] = file_listing
                n_files += subdir_n_files
                checksum.update(subdir_checksum.hexdigest().encode("utf-8"))

                progress.total = total_files
                progress.n = files_done
                progress.refresh()

            fileMD5 = hashlib.md5()
            file_listing = {}
            for name in files:
                if level == 0 and name == "tree_checksum.json":
                    # Skip the file that we created ourselves, but only at the top-level.
                    continue
                this_md5 = calculate_md5(dir, name)
                fileMD5.update(this_md5.hexdigest().encode("utf-8"))
                if detail_files:
                    file_listing[name] = {
                        "MD5": this_md5.hexdigest(),
                        "size": os.path.getsize(dir / name),
                        "last-modified-at": os.path.getmtime(dir / name),
                    }
                files_done += 1
            checksum.update(fileMD5.hexdigest().encode("utf-8"))

            return checksum, n_files, fileMD5, file_listing

        root_subdirectories: dict = {}
        checksum, n_files, fileMD5, file_listing = calculate_branch(root, root_subdirectories, 0)

    root_data = {
        "n_files": n_files,
        "subdirectories": root_subdirectories,
        "calculated_at": datetime.now().isoformat(),
        "MD5-files_only": fileMD5.hexdigest(),
        "MD5": checksum.hexdigest(),
    }
    if detail_files:
        root_data["file-listing"] = file_listing

    logger.info(f"A total of {n_files} files were enumerated.")
    logger.info(f"Checksum computed: {checksum.hexdigest()}")
    csum_file = root / "tree_checksum.json"
    logger.info(f"Saving checksum to file: {csum_file}")
    with open(csum_file, "wt") as outfile:
        json.dump(root_data, outfile)
    logger.info(f"Checksum saved.")


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

        for name in A_record["subdirectories"]:
            a_record = A_record["subdirectories"][name]
            if name not in B_record["subdirectories"]:
                msg += ("\t" * (level + 1)) + f"Directory '{name}' absent from B.\n"
                is_diff = True
        for name in B_record["subdirectories"]:
            b_record = B_record["subdirectories"][name]
            if name not in A_record["subdirectories"]:
                msg += ("\t" * (level + 1)) + f"Directory '{name}' absent from A.\n"
                is_diff = True

        # Once we find the levels where there are differences, we always want to
        # start incrementing the level.
        if level > 0 or is_diff:
            level += 1

        for name in set(A_record["subdirectories"].keys()).intersection(B_record["subdirectories"].keys()):
            a_record = A_record["subdirectories"][name]
            if name in B_record["subdirectories"]:
                b_record = B_record["subdirectories"][name]
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


def copy_tree_as_needed(source: Path, destination: Path):
    raise NotImplementedError("This functionality is not yet implemented, sorry.")


def main(args):
    logging.basicConfig(format="%(asctime)s.%(msecs)03d: %(message)s", datefmt="%Y-%j %H:%M:%S", level=logging.INFO)
    for handler in logging.getLogger().handlers:
        if isinstance(handler, logging.StreamHandler):
            handler.setLevel(logging.INFO)

    parser = argparse.ArgumentParser(
        description="Tool for collecting MD5 hashes of directory trees and selective copying"
    )
    parser.add_argument(
        "--calculate", type=str, default=None, help="Calculate the MD5 hash of the specified path and tree"
    )
    parser.add_argument(
        "--compare",
        type=str,
        nargs=2,
        default=None,
        metavar=("A", "B"),
        help="Compare checksum records for two paths and identify differences.",
    )
    parser.add_argument(
        "--copy",
        type=str,
        nargs=2,
        default=None,
        metavar=("source", "destination"),
        help="Copy the tree from [source] to [destination] where MD5s do not match.",
    )
    parser.add_argument(
        "--detail-files", action="store_true", help="Capture detailed file listings in the record file."
    )
    parser.add_argument("--v", action="store_true", help="Increase verbosity.")
    args = parser.parse_args(args)

    if args.v:
        for handler in logging.getLogger().handlers:
            if isinstance(handler, logging.StreamHandler):
                handler.setLevel(logging.DEBUG)
        logger.setLevel(logging.DEBUG)
        logger.debug(f"Debug-level verbosity enabled.")

    if args.calculate is not None:
        calculate_tree(Path(args.calculate), args.detail_files)
    elif args.copy is not None:
        source, destination = args.copy
        copy_tree_as_needed(Path(source), Path(destination))
    elif args.compare is not None:
        source, destination = args.compare
        compare_trees(Path(source), Path(destination))
    else:
        logger.error("No command was recognized on the command-line.")


if __name__ == "__main__":
    main(sys.argv)
