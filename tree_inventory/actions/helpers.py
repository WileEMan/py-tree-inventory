from __future__ import annotations

import hashlib
import json
import logging
import os
import subprocess
from pathlib import Path
from time import sleep
from typing import Any, Optional, Tuple, Union

from . import symlinks

logger = logging.getLogger(__name__)

PathOrStr = Union[Path, str]
# HASH = hashlib._hashlib.HASH


def find_key_by_value(dictionary: dict, value):
    return list(dictionary.keys())[list(dictionary.values()).index(value)]


AUTO = None


def calculate_md5_internal(pathname: Path, n_retries: Optional[int] = AUTO, _open_fcn=open) -> Any:
    block_size = 1 << 20  # Up to 1MB per chunk
    hash_md5 = hashlib.md5()
    # hash_md5.update(str(fname).encode("utf-8"))
    position = 0
    size = None
    retry = 0
    retries = 1
    while True:
        try:
            with _open_fcn(pathname, "rb") as f:
                if size is None:
                    f.seek(0, 2)
                    size = f.tell()
                    if n_retries is None:
                        n_retries = 1 + (size // (1 << 30))  # Allow 1 retry plus 1 retry per GB
                    retries = n_retries
                f.seek(position, 0)
                while True:
                    chunk = f.read(block_size)
                    if chunk == b"":
                        if retry > 0:
                            logger.info(f"Retry successful, completed checksum for: {pathname}")
                        return hash_md5
                    position += len(chunk)
                    hash_md5.update(chunk)
                # for chunk in iter(lambda: f.read(4096), b""):
                # hash_md5.update(chunk)
            # print(f"MD5 of file '{fname}': {hash_md5.hexdigest()}")
        except OSError as ose:
            if ose.errno == 22:
                retry += 1
                if retry <= retries:
                    block_size >>= 1
                    if block_size < 4096:
                        block_size = 4096
                    logger.warning(
                        f"Retrying ({retry} of {retries}) at position {position} while calculating checksum for: {pathname}..."
                    )
                    sleep(2)
                    continue
            raise


example_hash = "cefd9e43b97405a7a09628501004a0cb"


class hash_wrapper:
    def __init__(self, hexdigest: str):
        self._hexdigest = hexdigest

    def hexdigest(self):
        return self._hexdigest


def calculate_md5_certutil(pathname: Path, n_retries: Optional[int] = AUTO) -> Any:
    # certutil -hashfile <file> MD5
    if not (pathname.exists()):
        raise FileNotFoundError(f"Cannot calculate MD5 for file that is not found: {pathname}")
    process = subprocess.run(["certutil", "-hashfile", str(pathname), "MD5"], capture_output=True)
    stdout = process.stdout
    stderr = process.stderr
    returnvalue = process.returncode
    if returnvalue != 0:
        if returnvalue == 0x800703EE:
            # This error comes up for a zero-length file.  Let's verify that's the case and
            # provide a default.
            if pathname.stat().st_size == 0:
                return hashlib.md5()
        raise RuntimeError(f"MD5 calculation failed on file: {pathname}\n{stdout.decode()}\n{stderr.decode()}")
    try:
        data = stdout.decode("cp1252").replace("\r\n", "\n").replace("\n\r", "\n")
        lines = data.split("\n")
        if len(lines) != 4:
            raise RuntimeError(f"Expected certutil -hashfile command to output exactly 4 lines.")
        if "MD5" not in lines[0]:
            raise RuntimeError(f"Expected certutil -hashfile MD5 command to output a first line containing 'MD5'.")
        hashcode = lines[1]
        if len(hashcode) != len(example_hash):
            raise RuntimeError(
                f"Expected certutil -hashfile MD5 command to output a hash code of {len(example_hash)} digits, but received {len(hashcode)} digits instead: {hashcode}"
            )
        # print(f"certutil has exited with code: 0x{returnvalue:08x}")
        # print(f"STDOUT:\n{stdout}")
        # print(f"STDERR:\n{stderr}")
        return hash_wrapper(hashcode)
    except Exception as ex:
        if symlinks.islink(str(pathname)):
            raise FileNotFoundError(f"Cannot calculate MD5 for symlink/reparse point: {pathname}")

        raise RuntimeError(f"MD5 calculation failed on file: {pathname}\n{stdout.decode()}\n{stderr.decode()}") from ex


def calculate_md5(
    dirname: PathOrStr,
    fname: PathOrStr,
    n_retries: Optional[int] = AUTO,
    _open_fcn=open,
) -> Any:
    """Calculate the MD5 of a single file.  n_retries should normally be AUTO, but
    can specify a fixed number of retries allowed for the file."""
    pathname = Path(dirname) / fname
    try:
        if _open_fcn != open:
            return calculate_md5_internal(pathname, n_retries, _open_fcn)
        else:
            return calculate_md5_certutil(pathname, n_retries)

    except KeyboardInterrupt:
        logger.info(f"User abort (keyboard interrupt) while calculating checksum for file: {pathname}")
        raise

    except Exception as ex:
        raise RuntimeError(f"While calculating MD5 checksum for file: {pathname}: {str(ex)}") from ex


def record_summary(record: dict):
    """A helper for displaying a succinct summary of one record.  It will
    generally be used for looking at a specific record and not the entire
    record tree.
    """

    ret = "{"
    for key in record:
        if key == "subdirectories":
            subdirectories = record[key]
            ret += f"\n\t{key}: subdirectories: "
            if len(subdirectories) < 10:
                ret += ", ".join([name for name in subdirectories])
            else:
                ret += f"{str(len(record[key]))} subdirectories (not shown)"
        else:
            ret += f"\n\t{key}: {str(record[key])}"
    ret += "\n}"
    return ret


def enumerate_dir(dir: Path) -> Tuple[list, list]:
    """Perform the basic enumeration of files and folders within a directory."""

    subdirectories = []
    files = []
    for name in os.listdir(dir):
        if os.path.isdir(dir / name):
            subdirectories.append(name)
        else:
            files.append(name)
    # The order we calculate an MD5 hash matters, I believe, so sort them to be consistent.
    files.sort()
    subdirectories.sort()
    return files, subdirectories


def find_checksum_file(starting: Path):
    """If the user requests information or comparison about a folder, a first
    step will be to check whether there is a record file in the folder or at
    a higher-level than the folder.  This routine searches within the parent
    tree of the folder for a record file.  It returns None if there is no
    record file found.
    """
    attempt = starting / "tree_checksum.json"
    if attempt.exists():
        return attempt
    if starting.resolve() == starting.parent.resolve():
        # 'starting' is already the root...
        return None
    return find_checksum_file(starting.parent)


def read_checksum_file(checksum_file: Path) -> dict:
    """Read a record file."""
    with open(checksum_file, "rt") as fh:
        return json.load(fh)


def extract_record(root_record: dict, checksum_file: Path, target_path: Path) -> Tuple:
    """Once a record file is found and read, it may be necessary to locate
    a particular subrecord within the record tree.  For example, if the user
    wants to compare folders /root/A/AA and /root/B/AA but the record files
    are at the level of "A" and "B", then we need to first read the top-level
    record files and then locate the subrecord for AA within each.

    extract_record() returns a tuple described as relative_path, record_list.
    The record_list is a list which contains all the entries from the
    root to the target record.  To extract the highest-level record in the
    tree, use the first element in the list.  To extract the target record,
    use the last element in the list.
    """

    def descend_toward(target: tuple, base_record: dict):
        try:
            # print(f"Descending toward: {target}")
            next_target = target[0]
            if next_target not in base_record["subdirectories"]:
                raise RuntimeError(
                    f"While searching for the subdirectory entry for: {target_path}"
                    + f"\nIn checksum record file: {checksum_file}"
                    + f"\nThe subdirectory: {next_target}"
                    + f"\nWas not found in the record.  The checksum record might be out-of-date."
                )
            next_record = base_record["subdirectories"][next_target]
            if len(target) == 1:
                return [next_record]
            return [next_record] + descend_toward(target[1:], next_record)
        except Exception as ex:
            raise RuntimeError(
                str(ex)
                + f"\nWhile descending records toward: {target}"
                + f"\nFrom base record: \n{record_summary(base_record)}"
            ) from ex

    logger.debug(f"target_path = {target_path}")
    logger.debug(f"checksum_file = {checksum_file}")
    logger.debug(f"checksum_file.parent = {checksum_file.parent}")
    rel_path = target_path.relative_to(checksum_file.parent)
    if str(rel_path) == ".":
        return rel_path, [root_record]
    logger.debug(f"rel_path = {rel_path}")
    logger.debug(f"Searching for record for target: {rel_path}")
    return rel_path, [root_record] + descend_toward(rel_path.parts, root_record)


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
