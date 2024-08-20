import logging
import sys

from .main import main

if __name__ == "__main__":
    logging.basicConfig(
        format="%(asctime)s.%(msecs)03d: %(message)s",
        datefmt="%Y-%j %H:%M:%S",
        level=logging.INFO,
    )
    for handler in logging.getLogger().handlers:
        if isinstance(handler, logging.StreamHandler):
            handler.setLevel(logging.INFO)
    main(sys.argv[1:])
