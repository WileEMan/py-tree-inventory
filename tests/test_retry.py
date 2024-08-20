import logging

import numpy as np

# from tree_inventory.actions.helpers import calculate_md5

logger = logging.getLogger(__name__)


class SpecialTestFile:
    def __init__(self, file_size_GiB, value_changes_at, fails_at):
        self.position = 0
        self.n_fails_so_far = 0
        MiB = 1 << 20
        self.file_size = int(file_size_GiB * MiB)
        self.value_changes_at = (np.asarray(value_changes_at) * MiB).astype(int)
        self.fails_at = (np.asarray(fails_at) * MiB).astype(int)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def seek(self, offset, whence):
        if whence == 0:
            self.position = offset
        elif whence == 1:
            self.position += offset
        elif whence == 2:
            self.position = self.file_size + offset

    def tell(self):
        return self.position

    def read(self, max_amount: int) -> bytes:
        if self.n_fails_so_far < len(self.fails_at):
            next_failure = self.fails_at[self.n_fails_so_far]
            if (
                self.position <= next_failure
                and self.position + max_amount > next_failure
            ):
                logger.info(f"\tAt position {self.position}, generating OSError...")
                self.n_fails_so_far += 1
                raise OSError(22, "Invalid argument")

        endpoint_exclusive = min(self.position + max_amount, self.file_size)
        data = np.arange(self.position, endpoint_exclusive, dtype=int)
        for ii in range(len(self.value_changes_at)):
            value_change_at = self.value_changes_at[ii]
            rel_value_change_at = value_change_at - self.position
            if rel_value_change_at < endpoint_exclusive:
                data[rel_value_change_at:] += ii
        # if self.position >= endpoint_exclusive:
        # print(f"At EOF:\n\tposition = {self.position}\n\tendpoint_exclusive = {endpoint_exclusive}\n\tlen(data) = {len(data)}")
        self.position += len(data)
        data = (data % 256).astype(np.uint8)
        logger.info(f"\tReturning {len(data)}-byte block...")
        return data.tobytes()


def test_retry():
    """
    This is no longer relevant because I've replaced the MD5 calculation with a call
    to certutil.

    value_changes = [0.3, 0.9, 1.2, 1.8]
    breaks = [1.2, 3.4]

    def open_normal(filename, mode):
        return SpecialTestFile(7.13, value_changes, [])

    file_with_breaks = SpecialTestFile(7.13, value_changes, breaks)

    def open_breaks(filename, mode):
        nonlocal file_with_breaks
        return file_with_breaks

    logger.info(f"Calculating checksum for normal case...")
    csum_normal = calculate_md5("Irrelevant", "Irrelevant", n_retries=5, _open_fcn=open_normal)
    logger.info(f"Checksum: {csum_normal.hexdigest()}\n")
    logger.info(f"Calculating checksum for disconnecting case...")
    csum_breaks = calculate_md5("Irrelevant", "Irrelevant", n_retries=5, _open_fcn=open_breaks)
    logger.info(f"Checksum: {csum_breaks.hexdigest()}\n")
    assert csum_normal.hexdigest() == csum_breaks.hexdigest()
    logger.info(f"Success.")
    """


if __name__ == "__main__":
    logging.basicConfig(
        format="%(asctime)s.%(msecs)03d: %(message)s",
        datefmt="%Y-%j %H:%M:%S",
        level=logging.INFO,
    )
    for handler in logging.getLogger().handlers:
        if isinstance(handler, logging.StreamHandler):
            handler.setLevel(logging.INFO)
    test_retry()
