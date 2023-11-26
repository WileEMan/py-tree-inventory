import os
import json
import logging
import hashlib
from tqdm import tqdm
from pathlib import Path
from datetime import datetime
from time import perf_counter, sleep
from typing import Callable, Optional

from .helpers import (
    calculate_md5,
    enumerate_dir,
    read_checksum_file,
    find_checksum_file,
    extract_record,
    find_key_by_value,
)

logger = logging.getLogger(__name__)


class Calculator:
    def __init__(self, continue_previous: bool = False, detail_files: bool = False):
        self.on_occasion: Optional[Callable] = None
        self.continue_previous = continue_previous
        self.detail_files = detail_files
        self.total_files = 0
        self.files_done = 0
        self.last_occasion = perf_counter()
        self.between_occasions = 10.0
        self.verbose = False
        self.very_verbose = False

    def _do_occasion(self):
        self.last_occasion = perf_counter()
        if self.on_occasion is not None:
            self.on_occasion()
        elapsed = perf_counter() - self.last_occasion
        if elapsed < 2.0:
            self.between_occasions = 60.0
        else:
            self.between_occasions = elapsed * 25

    def calculate_branch(self, record: dict, dir: Path, level: int):
        if perf_counter() - self.last_occasion > self.between_occasions:
            self._do_occasion()

        checksum = hashlib.md5()
        files, subdirectories = enumerate_dir(dir)
        self.total_files += len(files) + len(subdirectories)

        if self.verbose:
            logger.debug(f"Initial MD5 is: {checksum.hexdigest()}")
        if len(subdirectories) > 0:
            if not self.continue_previous or "subdirectories" not in record:
                record["subdirectories"] = {}
            for name in subdirectories:
                checksum.update(name.encode("utf-8"))
                sub_record = (
                    {}
                    if (not (self.continue_previous) or name not in record["subdirectories"])
                    else record["subdirectories"][name]
                )
                record["subdirectories"][name] = sub_record
                if "MD5" not in sub_record:
                    self.calculate_branch(sub_record, dir / name, level + 1)
                checksum.update(sub_record["MD5"].encode("utf-8"))
                self.files_done += 1
                if perf_counter() - self.last_occasion > self.between_occasions:
                    self._do_occasion()

        if self.verbose:
            logger.debug(f"After subdirectories, MD5 is: {checksum.hexdigest()}")
        fileMD5 = hashlib.md5()
        n_files = 0
        if self.detail_files:
            file_listing = record["file-listing"] = {}
        for name in files:
            if level == 0 and name == "tree_checksum.json":
                # Skip the file that we created ourselves, but only at the top-level.
                self.files_done += 1
                continue
            n_files += 1
            this_md5 = calculate_md5(dir, name)
            fileMD5.update(this_md5.hexdigest().encode("utf-8"))
            if self.very_verbose:
                logger.debug(f"After file '{name}', MD5-files_only is: {fileMD5.hexdigest()}")
            if self.detail_files:
                file_listing[name] = {
                    "MD5": this_md5.hexdigest(),
                    "size": os.path.getsize(dir / name),
                    "last-modified-at": os.path.getmtime(dir / name),
                }
            self.files_done += 1
            if perf_counter() - self.last_occasion > self.between_occasions:
                self._do_occasion()
        checksum.update(fileMD5.hexdigest().encode("utf-8"))
        if self.verbose:
            logger.debug(f"After files, MD5 is: {checksum.hexdigest()}")
        record["n_files"] = n_files
        record["MD5-files_only"] = fileMD5.hexdigest()

        record["MD5"] = checksum.hexdigest()
        return

    def recalculate(self, record: dict):
        checksum = hashlib.md5()
        for name in record["subdirectories"]:
            checksum.update(name.encode("utf-8"))
            sub_record = record["subdirectories"][name]
            if "MD5" not in sub_record:
                # Invalidated record, so can't calculate higher in the tree either.
                raise RuntimeError(
                    f"Cannot recalculate this record because one or more sub-records does not have a completed checksum."
                )
            checksum.update(sub_record["MD5"].encode("utf-8"))
        fileMD5_str = record["MD5-files_only"]
        checksum.update(fileMD5_str.encode("utf-8"))
        record["MD5"] = checksum.hexdigest()
        return


def calculate_tree(target: Path, continue_previous: bool = False, start_new: bool = False, detail_files: bool = False):
    """calculate_tree() implements the main record calculation facility
    of tree_inventory and is invoked via the --calculate command-line
    option.
    """

    if start_new and continue_previous:
        raise RuntimeError("Cannot specify both --new and --continue at the same time.")

    logger.info(f"Calculating checksum for path '{target}'...")

    root_record = None
    target_record = None
    parent_records = []
    if start_new:
        csum_record_file = target / "tree_checksum.json"

        higher_csum_record_file = find_checksum_file(target)
        if (
            higher_csum_record_file is not None
            and higher_csum_record_file.exists()
            and not (os.path.samefile(higher_csum_record_file, csum_record_file))
        ):
            logger.warning(f"Starting a new record file at: {csum_record_file}")
            logger.warning(f"However a higher-level record file was found at: {higher_csum_record_file}")
            logger.warning(f"Note that further operations will utilize the highest-level record found automatically.")
            logger.warning(
                f"Consider removing --new from your command or deleting the higher-level record if not intentional."
            )
            sleep(5)
            logger.warning(f"Proceeding as requested.")

        if csum_record_file.exists():
            csum_record_file.unlink()
        root_record = target_record = {}
        target_record["calculated_at"] = datetime.now().isoformat()
    else:
        csum_record_file = find_checksum_file(target)
        if csum_record_file is None or not csum_record_file.exists():
            csum_record_file = target / "tree_checksum.json"
            root_record = target_record = {}
            target_record["calculated_at"] = datetime.now().isoformat()
        else:
            logger.info(f"Updating existing checksum file found at: {csum_record_file}")
            root_record = read_checksum_file(csum_record_file)
            _, parent_records = extract_record(root_record, csum_record_file, target)
            target_record = parent_records[-1]
            parent_records = parent_records[:-1]
            if not (continue_previous):
                # target_record still needs to be referenced by its parent, but everything within
                # it can be wiped out.  So can't create a new dictionary here, but can use clear().
                target_record.clear()
                target_record["calculated_at"] = datetime.now().isoformat()

    # Mark all parent records as invalidated until we complete.
    for ii in range(len(parent_records)):
        del parent_records[ii]["MD5"]

    parent_records_subdir_names = [
        find_key_by_value(parent_records[ii - 1]["subdirectories"], parent_records[ii])
        for ii in range(1, len(parent_records))
    ]
    parent_records_str = "root / " + " / ".join(parent_records_subdir_names)
    logger.debug(f"parent records = {parent_records_str}")

    with tqdm(total=1) as progress:
        calc = Calculator(continue_previous, detail_files)
        # calc.verbose = True
        # calc.very_verbose = True

        def save_record(final: bool):
            nonlocal root_record

            logger.info(f"Saving checksum to file: {csum_record_file}")

            if final:
                for ii in range(len(parent_records) - 1, -1, -1):
                    calc.recalculate(parent_records[ii])

            with open(csum_record_file, "wt") as outfile:
                json.dump(root_record, outfile, indent=4)

        def on_occasion():
            nonlocal progress, calc

            progress.total = calc.total_files
            progress.n = calc.files_done
            progress.refresh()

            save_record(final=False)

        calc.on_occasion = on_occasion
        calc.calculate_branch(target_record, target, len(parent_records))
    save_record(final=True)
    logger.info(f"Done.")
