import sys
import argparse
import logging
import traceback
from pathlib import Path
from typing import Union


from .actions.calculate import calculate_tree
from .actions.compare import compare_trees
from .actions.update import update_copy

logger = logging.getLogger(__name__)

PathOrStr = Union[Path, str]


def main(args):
    try:
        parser = argparse.ArgumentParser(
            description="Tool for collecting MD5 hashes of directory trees and selective copying"
        )
        parser.add_argument(
            "--calculate", type=str, default=None, help="Calculate the MD5 hash of the specified path and tree"
        )
        parser.add_argument(
            "--continue",
            dest="continue_previous",
            action="store_true",
            help="Continue calculation from where it left off",
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
            "--update",
            type=str,
            nargs=2,
            default=None,
            metavar=("source", "destination"),
            help="Update the tree from [source] to [destination] where MD5s do not match.",
        )
        parser.add_argument(
            "--dry-run", action="store_true", help="A listing of all changes will be produced but no changes made."
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
            calculate_tree(Path(args.calculate), args.continue_previous, args.detail_files)
        elif args.update is not None:
            source, destination = args.update
            update_copy(Path(source), Path(destination), dry_run=args.dry_run)
        elif args.compare is not None:
            source, destination = args.compare
            compare_trees(Path(source), Path(destination))
        else:
            raise RuntimeError("No command was recognized on the command-line.")

    except Exception as ex:
        print(str(ex))
        logger.error(traceback.format_exc())


if __name__ == "__main__":
    logging.basicConfig(format="%(asctime)s.%(msecs)03d: %(message)s", datefmt="%Y-%j %H:%M:%S", level=logging.INFO)
    for handler in logging.getLogger().handlers:
        if isinstance(handler, logging.StreamHandler):
            handler.setLevel(logging.INFO)
    main(sys.argv)
