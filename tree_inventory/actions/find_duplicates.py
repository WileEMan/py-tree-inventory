# TODO: no unit tests on find_duplicates.

import logging
from pathlib import Path
from typing import Union

from .helpers import extract_record, find_checksum_file, read_checksum_file

logger = logging.getLogger(__name__)

PathOrStr = Union[Path, str]


def find_duplicates(A: Path, count: int = -1):
    """find_duplicates() searches for duplication within an
    already-calculated tree inventory.  It descends the tree and
    creates a map of all checksums.  Before adding each new checksum,
    the map (hashtable) is checked for whether the checksum is already
    a key in the hashtable.  If it is, and the size matches, then a
    duplicate is identified and added to the duplicates list.  The
    duplicates list is then sorted by size and saved to duplicates.csv.
    """

    logger.info(f"Searching for duplicate folders within:\n\t{A}")
    A_record_file = find_checksum_file(A)
    logger.debug(f"Checksum file found at: {A_record_file}")
    root_path = Path(A_record_file).parent
    A_record = read_checksum_file(A_record_file)
    A_rel_path, A_records = extract_record(A_record, A_record_file, A)
    A_subrecord = A_records[-1]

    # For example, if the argument 'A' was:
    #   D:\Top\Second\Third
    # but the record file was found in D:\Top\tree_checksum.json, then:
    #   A_rel_path = r"Second\Third"
    #   A_subrecord is the record specifically for 'Third'.

    # Build a hash table from the MD5s.  Anytime that a duplicate MD5 is detected, add an entry to the duplicates list.
    duplicates: list = []
    hashtable: dict = {}

    def is_already_duplicate(old_entry, new_entry):
        # Detect if this duplication is already listed as part of a higher-level
        # directory in the tree.
        nonlocal duplicates

        new_record_A, new_rel_path_A = old_entry
        new_record_B, new_rel_path_B = new_entry

        for entry in duplicates:
            size, dupe_A, dupe_B = entry
            existing_record_A, existing_rel_path_A = dupe_A
            existing_record_B, existing_rel_path_B = dupe_B
            if (
                new_rel_path_A.is_relative_to(existing_rel_path_A)
                and new_rel_path_B.is_relative_to(existing_rel_path_B)
            ) or (
                new_rel_path_B.is_relative_to(existing_rel_path_A)
                and new_rel_path_A.is_relative_to(existing_rel_path_B)
            ):
                return True
        return False

    def collect_checksums(rel_path: str, record: dict, is_within_duplicates: bool = False):
        nonlocal duplicates, hashtable

        new_size = record["size"]
        if new_size < 1:
            return

        checksum = record["MD5"]
        new_entry = (record, rel_path)
        if checksum in hashtable:
            if not is_within_duplicates:
                for old_entry in hashtable[checksum]:
                    old_record, old_rel_path = old_entry
                    if old_record["size"] == new_size:
                        if not is_already_duplicate(old_entry, new_entry):
                            duplicates.append((new_size, old_entry, new_entry))
                        is_within_duplicates = True
                        break
            hashtable[checksum].append(new_entry)
        else:
            hashtable[checksum] = [new_entry]

        subdirectories = record["subdirectories"] if "subdirectories" in record else {}
        for name in subdirectories:
            rel_sub_path = Path(rel_path) / name
            collect_checksums(rel_sub_path, subdirectories[name], is_within_duplicates)

    logger.info(f"Looking for duplicates in: {root_path / A_rel_path}")
    collect_checksums(A_rel_path, A_subrecord)
    logger.info(f"{len(duplicates)} duplicate folders were found.")

    # Sort duplicates by size
    duplicates.sort(reverse=True, key=lambda x: x[0])

    # Save results in duplicates.csv.
    with open("duplicates.csv", "wt") as fh:
        fh.write('"Size (in bytes)","Folder Path","Duplicate Folder Path",\n')
        for dupe in duplicates:
            size = dupe[0]
            record1, rel_path1 = dupe[1]
            record2, rel_path2 = dupe[2]
            fh.write(f'"{size}","{rel_path1}","{rel_path2}",\n')

    logger.info(f"Duplicates list saved to duplicates.csv.")
