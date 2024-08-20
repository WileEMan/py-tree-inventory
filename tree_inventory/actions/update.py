import json
import logging
import os
import shutil
from pathlib import Path
from time import perf_counter
from typing import Union

from tqdm import tqdm

from .calculate import Calculator
from .helpers import enumerate_dir, extract_record, find_checksum_file, print_file, read_checksum_file

logger = logging.getLogger(__name__)

PathOrStr = Union[Path, str]


def update_copy(source: Path, destination: Path, dry_run: bool = False):
    """Perform an update of the destination path from the source with the
    tree inventory as a resource to minimize the effort."""

    logger.info(f"Updating tree:\n\tFrom source: {source}\n\tTo destination: {destination}")
    src_record_file = find_checksum_file(source)
    if src_record_file is None or not src_record_file.exists():
        raise RuntimeError(
            f"Checksum record file not found for source: {source}" + f"\nTry running --calculate before --update"
        )
    logger.debug(f"Checksum file SRC found at: {src_record_file}")
    src_record = read_checksum_file(src_record_file)
    src_rel_path, src_records = extract_record(src_record, src_record_file, source)
    src_subrecord = src_records[-1]

    dst_record_file = find_checksum_file(destination)
    if dst_record_file is not None and dst_record_file.exists():
        dst_record = read_checksum_file(dst_record_file)
        dst_rel_path, dst_records = extract_record(dst_record, dst_record_file, destination)
        dst_subrecord = dst_records[-1]
        logger.debug(f"Checksum file DST found at: {dst_record_file}")
    else:
        raise RuntimeError(
            f"Checksum record file not found for destination: {destination}"
            + f"\nTry running --calculate before --update"
        )
        """
        dst_record = {}
        dst_record["calculated_at"] = datetime.now().isoformat()
        dst_record_file = destination / "tree_checksum.json"
        dst_subrecord = dst_record
        """

    if src_rel_path != dst_rel_path:
        raise RuntimeError(
            f"After locating the subdirectory of interest in trees A and B, the relative paths do not match:"
            + f"\n\tRelative path SRC: {src_rel_path}"
            + f"\n\tRelative path DST: {dst_rel_path}"
        )

    with tqdm(total=1) as progress:
        calc = Calculator(True, False)

        def update_branch(
            SRC_path: Path,
            DST_path: Path,
            SRC_record: dict,
            DST_record: dict,
            level: int,
        ):
            if (
                "MD5" in DST_record
                and "n_files" in DST_record
                and SRC_record["MD5"] == DST_record["MD5"]
                and SRC_record["n_files"] == DST_record["n_files"]
            ):
                return

            ## Update files, if needed

            if "MD5-files_only" not in DST_record or DST_record["MD5-files_only"] != SRC_record["MD5-files_only"]:
                SRC_files, _ = enumerate_dir(SRC_path)
                DST_files, _ = enumerate_dir(DST_path)

                for name in SRC_files:
                    if level == 0 and name == "tree_checksum.json":
                        # Skip the file that we created ourselves, but only at the top-level.
                        continue
                    src_file = SRC_path / name
                    dst_file = DST_path / name
                    if dry_run:
                        verb = "overwrite" if dst_file.exists() else "copy"
                        logger.info(f"\tWould {verb} file: {src_file} -> {dst_file}")
                    else:
                        shutil.copy(src_file, dst_file)
                    if perf_counter() - calc.last_occasion > calc.between_occasions:
                        calc._do_occasion()

                for name in DST_files:
                    if level == 0 and name == "tree_checksum.json":
                        # Skip the file that we created ourselves, but only at the top-level.
                        continue
                    if name not in SRC_files:
                        rm_path = DST_path / name
                        if dry_run:
                            logger.info(f"\tWould remove file: {rm_path}")
                        else:
                            logger.info(f"\tRemoving file: {rm_path}")
                            os.remove(rm_path)
                    if perf_counter() - calc.last_occasion > calc.between_occasions:
                        calc._do_occasion()

            ## Update directories

            SRC_subdirectories = SRC_record["subdirectories"] if "subdirectories" in SRC_record else {}
            DST_subdirectories = DST_record["subdirectories"] if "subdirectories" in DST_record else {}
            print(f"\nSRC_path = {SRC_path}")
            print(f"SRC_subdirectories = {SRC_subdirectories.keys()}")
            print(f"DST_subdirectories = {DST_subdirectories.keys()}")
            for name in SRC_subdirectories:
                src_subrecord = SRC_subdirectories[name]
                if name not in DST_subdirectories:
                    from_dir = SRC_path / name
                    to_dir = DST_path / name
                    logger.debug(f"Copying {from_dir} -> {to_dir}")
                    shutil.copytree(from_dir, to_dir)
                else:
                    dst_subrecord = DST_subdirectories[name]
                    update_branch(
                        SRC_path / name,
                        DST_path / name,
                        src_subrecord,
                        dst_subrecord,
                        level + 1,
                    )
            removed = []
            for name in DST_subdirectories:
                if name not in SRC_subdirectories:
                    rm_path = DST_path / name
                    if dry_run:
                        logger.info(f"Would remove tree: {rm_path}")
                    else:
                        logger.info(f"Removing tree: {rm_path}")
                        shutil.rmtree(rm_path)
                    removed.append(name)
            for key in removed:
                DST_subdirectories.pop(key)

            # Having copied the files and subtrees, update the destination record.
            if not (dry_run):
                calc.calculate_branch(DST_record, DST_path, level)
            return

        def save_record():
            nonlocal dst_record

            logger.info(f"Saving checksum to file: {dst_record_file}")
            with open(dst_record_file, "wt") as outfile:
                json.dump(dst_record, outfile)

        def on_occasion():
            nonlocal progress, calc

            progress.total = calc.total_files
            progress.n = calc.files_done
            progress.refresh()

            save_record()

        calc.on_occasion = on_occasion
        print_file(src_record_file)
        print_file(dst_record_file)
        update_branch(source, destination, src_subrecord, dst_subrecord, 0)
    save_record()
    logger.info(f"Done.")
