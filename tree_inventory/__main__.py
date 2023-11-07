import os
import sys
import argparse
import hashlib
import json
import logging
from tqdm import tqdm
from pathlib import Path
from datetime import datetime
from typing import Tuple, Union

logger = logging.getLogger(__name__)


PathOrStr = Union[Path, str]

def calculate_md5(dirname: PathOrStr, fname: PathOrStr) -> hashlib.md5:
    hash_md5 = hashlib.md5()
    hash_md5.update(str(fname).encode("utf-8"))
    with open(Path(dirname) / fname, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    # print(f"MD5 of file '{fname}': {hash_md5.hexdigest()}")
    return hash_md5


def record_summary(record: dict):
    ret = "{"
    for key in record:
        if key == "subdirectories":
            subdirectories = record[key]
            ret += f"\n\t{key}: subdirectories: "
            if len(subdirectories) < 10:
                ret += ', '.join([name for name in subdirectories])
            else:
                ret += f"{str(len(record[key]))} subdirectories (not shown)"
        else:
            ret += f"\n\t{key}: {str(record[key])}"
    ret += "\n}"
    return ret


def enumerate_dir(dir: Path) -> Tuple[list, list]:
    subdirectories = []
    files = []
    for name in os.listdir(dir):
        if os.path.isdir(dir / name):
            subdirectories.append(name)
        else:
            files.append(name)
    return files, subdirectories

def do_calculate_tree(root: Path):
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
                subcollection = {}
                subdir_checksum, subdir_n_files, fileMD5 = calculate_branch(dir / name, subcollection, level + 1)
                collection[name] = {
                    "n_files": n_files,
                    "subdirectories": subcollection,
                    "MD5": subdir_checksum.hexdigest(),
                    "files_only_MD5": fileMD5.hexdigest()
                }
                n_files += subdir_n_files
                checksum.update(subdir_checksum.hexdigest().encode('utf-8'))

                progress.total = total_files
                progress.n = files_done
                progress.refresh()

            fileMD5 = hashlib.md5()
            for name in files:
                fileMD5.update(calculate_md5(dir, name).hexdigest().encode("utf-8"))
                files_done += 1
            checksum.update(fileMD5.hexdigest().encode("utf-8"))

            return checksum, n_files, fileMD5

        root_subdirectories = {}
        checksum, n_files, fileMD5 = calculate_branch(root, root_subdirectories, 0)

    root_data = {
        "n_files": n_files,
        "subdirectories": root_subdirectories,
        "calculated_at": datetime.now().isoformat(),
        "files_only_MD5": fileMD5.hexdigest(),
        "MD5": checksum.hexdigest()
    }

    logger.info(f"A total of {n_files} files were enumerated.")
    logger.info(f"Checksum computed: {checksum.hexdigest()}")
    csum_file = root / "tree_checksum.json"
    logger.info(f"Saving checksum to file: {csum_file}")
    with open(csum_file, "wt") as outfile:
        json.dump(root_data, outfile)
    logger.info(f"Checksum saved.")


def find_checksum_file(starting: Path):
    attempt = starting / "tree_checksum.json"
    if attempt.exists():
        return attempt
    if starting.resolve() == starting.parent.resolve():
        # 'starting' is already the root...
        return None
    return find_checksum_file(starting.parent)


def read_checksum_file(checksum_file: Path):
    with open(checksum_file, "rt") as fh:
        return json.load(fh)


def extract_record(root_record: dict, checksum_file: Path, target_path: Path):
    def descend_toward(target: tuple, base_record: dict):
        try:
            print(f"Descending toward: {target}")
            first_dir = target[0]
            if first_dir not in base_record["subdirectories"]:
                raise RuntimeError(
                    f"While searching for the subdirectory entry for: {target_path}"
                    + f"\nIn checksum record file: {checksum_file}"
                    + f"\nThe subdirectory: {first_dir}"
                    + f"\nWas not found in the record.  The checksum record might be out-of-date."
                )
            next_record = base_record["subdirectories"][first_dir]
            if len(target) == 1:
                return next_record
            return descend_toward(target[1:], next_record)
        except Exception as ex:
            raise RuntimeError(str(ex)
                               + f"\nWhile descending records toward: {target}"
                               + f"\nFrom base record: \n{record_summary(base_record)}") from ex

    logger.debug(f"target_path = {target_path}")
    logger.debug(f"checksum_file = {checksum_file}")
    logger.debug(f"checksum_file.parent = {checksum_file.parent}")
    rel_path = target_path.relative_to(checksum_file.parent)
    if str(rel_path) == ".":
        return rel_path, root_record
    logger.debug(f"rel_path = {rel_path}")
    logger.debug(f"Searching for record for target: {rel_path}")
    return rel_path, descend_toward(rel_path.parts, root_record)


def compare_trees(A: Path, B: Path):
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
        if A_record["MD5"] == B_record["MD5"] and A_record["n_files"] == B_record["n_files"]:
            return ""
        if level >= 3:
            return ""

        is_diff = False
        msg = ""
        if A_record["files_only_MD5"] != B_record["files_only_MD5"]:
            msg += ('\t' * (level+1)) + f"Files within this folder mismatch.\n"
            is_diff = True

        # Check if any subdirectories are absent first

        for name in A_record["subdirectories"]:
            a_record = A_record["subdirectories"][name]
            if name not in B_record["subdirectories"]:
                msg += ('\t' * (level+1)) + f"Directory '{name}' absent from B.\n"
                is_diff = True
        for name in B_record["subdirectories"]:
            b_record = B_record["subdirectories"][name]
            if name not in A_record["subdirectories"]:
                msg += ('\t' * (level+1)) + f"Directory '{name}' absent from A.\n"
                is_diff = True

        # Once we find the levels where there are differences, we always want to
        # start incrementing the level.
        if level > 0 or is_diff:
            level += 1

        for name in set(A_record["subdirectories"].keys()).union(B_record["subdirectories"].keys()):
            a_record = A_record["subdirectories"][name]
            if name in B_record["subdirectories"]:
                b_record = B_record["subdirectories"][name]
                msg += compare_branch(A_base_path / name, B_base_path / name, a_record, b_record, level)

        if len(msg) > 0:
            msg = ('\t' * (level-1)) + f"{A_base_path} (A) vs {B_base_path} (B):\n" + msg

        return msg


    A_base_path = A_record_file.parent / A_rel_path
    B_base_path = B_record_file.parent / B_rel_path
    result = compare_branch(A_base_path, B_base_path, A_subrecord, B_subrecord, 0)
    if not(result):
        result = "\tNo differences found.\n"
    result = f"\n\nAs of {A_record['calculated_at']} (A) and {B_record['calculated_at']} (B):\n" + result
    logger.info(result)


def do_copy_tree(source: Path, destination: Path):
    raise NotImplementedError()


def main(args):
    logging.basicConfig(format="%(asctime)s.%(msecs)03d: %(message)s", datefmt="%Y-%j %H:%M:%S", level=logging.INFO)
    for handler in logging.getLogger().handlers:
        if isinstance(handler, logging.StreamHandler):
            handler.setLevel(logging.INFO)

    parser = argparse.ArgumentParser(description="Tool for collecting MD5 hashes of directory trees and selective copying")
    parser.add_argument("--calculate", type=str, default=None, help="Calculate the MD5 hash of the specified path and tree")
    parser.add_argument("--compare", type=str, nargs=2, default=None,
                        metavar=("A", "B"),
                        help="Compare checksum records for two paths and identify differences.")
    parser.add_argument("--copy", type=str, nargs=2, default=None,
                        metavar=("source", "destination"),
                        help="Copy the tree from [source] to [destination] where MD5s do not match.")
    parser.add_argument("--v", action="store_true",
                        help="Increase verbosity.")
    args = parser.parse_args(args)

    if args.v:
        for handler in logging.getLogger().handlers:
            if isinstance(handler, logging.StreamHandler):
                handler.setLevel(logging.DEBUG)
        logger.setLevel(logging.DEBUG)
        logger.debug(f"Debug-level verbosity enabled.")

    if args.calculate is not None:
        do_calculate_tree(Path(args.calculate))
    elif args.copy is not None:
        source, destination = args.copy
        do_copy_tree(Path(source), Path(destination))
    elif args.compare is not None:
        source, destination = args.compare
        compare_trees(Path(source), Path(destination))
    else:
        logger.error("No command was recognized on the command-line.")

if __name__ == "__main__":
    main(sys.args)