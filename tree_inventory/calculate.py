import os
import hashlib
from time import perf_counter
from pathlib import Path
from typing import Callable

from .helpers import calculate_md5, enumerate_dir


class Calculator:
    def __init__(self, on_occasion: Callable, continue_previous: bool = False, detail_files: bool = False):
        self.on_occasion = on_occasion
        self.continue_previous = continue_previous
        self.detail_files = detail_files
        self.total_files = 0
        self.files_done = 0
        self.last_occasion = perf_counter()
        self.between_occasions = 60.0

    def _do_occasion(self):
        self.last_occasion = perf_counter()
        self.on_occasion()
        elapsed = perf_counter() - self.last_occasion
        if elapsed < 2.0:
            self.between_occasions = 60.0
        else:
            self.between_occasions = elapsed * 25

    def calculate_branch(self, record: dict, dir: Path, level: int):
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
