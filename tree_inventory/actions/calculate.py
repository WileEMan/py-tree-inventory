import os
import json
import logging
import hashlib
from tqdm import tqdm
from pathlib import Path
from datetime import datetime
from time import perf_counter
from typing import Callable, Optional

from .helpers import calculate_md5, enumerate_dir, read_checksum_file

logger = logging.getLogger(__name__)


class Calculator:
    def __init__(self, continue_previous: bool = False, detail_files: bool = False):
        self.on_occasion: Optional[Callable] = None
        self.continue_previous = continue_previous
        self.detail_files = detail_files
        self.total_files = 0
        self.files_done = 0
        self.last_occasion = perf_counter()
        self.between_occasions = 60.0

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
        record["n_files"] = n_files
        record["MD5-files_only"] = fileMD5.hexdigest()

        record["MD5"] = checksum.hexdigest()
        return


def calculate_tree(root: Path, continue_previous: bool = False, detail_files: bool = False):
    """calculate_tree() implements the main record calculation facility
    of tree_inventory and is invoked via the --calculate command-line
    option.
    """

    logger.info(f"Calculating checksum for path '{root}'...")
    csum_file = root / "tree_checksum.json"
    with tqdm(total=1) as progress:
        calc = Calculator(continue_previous, detail_files)

        if continue_previous:
            if csum_file.exists():
                root_record = read_checksum_file(csum_file)
            else:
                continue_previous = False
        if not continue_previous:
            root_record = {}
            root_record["calculated_at"] = datetime.now().isoformat()

        def save_record():
            nonlocal root_record

            logger.info(f"Saving checksum to file: {csum_file}")
            with open(csum_file, "wt") as outfile:
                json.dump(root_record, outfile)

        def on_occasion():
            nonlocal progress, calc

            progress.total = calc.total_files
            progress.n = calc.files_done
            progress.refresh()

            save_record()

        calc.on_occasion = on_occasion
        calc.calculate_branch(root_record, root, 0)
    save_record()
    logger.info(f"Done.")
