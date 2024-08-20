import argparse
import logging
import traceback
from pathlib import Path
from typing import Union

from .actions.calculate import calculate_tree
from .actions.compare import compare_trees
from .actions.find_duplicates import find_duplicates
from .actions.update import update_copy

logger = logging.getLogger(__name__)

PathOrStr = Union[Path, str]


def main(args):
    try:
        parser = argparse.ArgumentParser(
            description="Tool for collecting MD5 hashes of directory trees and selective copying",
            epilog="Note: if you apply --calculate on a directory within a tree that has already been calculated, then"
            + " that directory will be recalculated from scratch and the result updated within the parent tree records,"
            + " unless --new is also used.",
        )
        parser.add_argument(
            "--calculate",
            type=str,
            default=None,
            help="Calculate the MD5 hash of the specified path and tree",
        )
        parser.add_argument(
            "--new",
            dest="start_new",
            action="store_true",
            help="Do not utilize existing calculations.",
        )
        parser.add_argument(
            "--continue",
            dest="continue_previous",
            action="store_true",
            help="Perform calculation only on unfinished parts of previous calculation.",
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
            "--depth",
            type=int,
            default=2,
            help="Maximum depth for comparing two trees.",
        )
        parser.add_argument(
            "--update",
            type=str,
            nargs=2,
            default=None,
            metavar=("source", "destination"),
            help="Update the tree from [source] to [destination] where MD5s do not match.",
        )
        parser.add_argument(
            "--find-duplicates",
            type=str,
            default=None,
            metavar="PATH",
            help="Identify the largest duplicate folders within the path and save to duplicates.csv.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="A listing of all changes will be produced but no changes made.",
        )
        parser.add_argument(
            "--detail-files",
            action="store_true",
            help="Capture detailed file listings in the record file.",
        )
        parser.add_argument(
            "--parallel",
            type=int,
            default=1,
            help="Perform the operation with specified number of threads where supported.",
        )
        parser.add_argument(
            "-v", "--v", action="store_true", help="Increase verbosity."
        )
        args = parser.parse_args(args)

        if args.v:
            for handler in logging.getLogger().handlers:
                if isinstance(handler, logging.StreamHandler):
                    handler.setLevel(logging.DEBUG)
            logging.getLogger().setLevel(logging.DEBUG)
            logger.setLevel(logging.DEBUG)
            logger.debug(f"Debug-level verbosity enabled.")

        if args.calculate is not None:
            calculate_tree(
                Path(args.calculate),
                args.continue_previous,
                args.start_new,
                args.detail_files,
                args.parallel,
                args.v,
            )
        elif args.update is not None:
            source, destination = args.update
            update_copy(Path(source), Path(destination), dry_run=args.dry_run)
        elif args.compare is not None:
            source, destination = args.compare
            compare_trees(Path(source), Path(destination), depth=args.depth)
        elif args.find_duplicates is not None:
            target = args.find_duplicates
            find_duplicates(Path(target))
        else:
            raise RuntimeError("No command was recognized on the command-line.")

    except Exception as ex:
        print(str(ex))
        logger.error(traceback.format_exc())
