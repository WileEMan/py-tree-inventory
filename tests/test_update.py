from time import sleep
import shutil
import logging
from pathlib import Path

from t_helpers import write_text_to_file, main_with_log, parse_results

logger = logging.getLogger(__name__)


def test_update():
    addn_options = ["--v", "--detail-files"]

    this_dir = Path(__file__).parent
    resources_path = this_dir / "resources"
    temp_path_A = this_dir / "tempA"
    temp_path_B = this_dir / "tempB"
    if temp_path_A.exists():
        shutil.rmtree(temp_path_A)
    if temp_path_B.exists():
        shutil.rmtree(temp_path_B)
    try:
        shutil.copytree(resources_path, temp_path_A)
        shutil.copytree(resources_path, temp_path_B)
        sleep(1)

        ###
        ### Test 'update mode' where we copy/overwrite/remove files as needed
        ###

        # Add a file and directory to A to be copied with the update
        write_text_to_file(temp_path_A / "Folder_B" / "New_Folder" / "update_file_1.txt", "A file to be transferred.")
        main_with_log(["--calculate", str(temp_path_A)] + addn_options)

        # Add a file and directory to B to be removed with the update
        write_text_to_file(temp_path_B / "Folder_C" / "Unwanted_Folder" / "update_file_2.txt", "A file to be removed.")
        main_with_log(["--calculate", str(temp_path_B)] + addn_options)

        test = main_with_log(["--compare", str(temp_path_A), str(temp_path_B)] + addn_options)
        file_mismatches, missing_A, missing_B = parse_results(test, temp_path_A, temp_path_B)
        assert len(file_mismatches) == 0
        assert missing_A == ["Unwanted_Folder"]
        assert missing_B == ["New_Folder"]

        main_with_log(["--update", str(temp_path_A), str(temp_path_B)] + addn_options)

        test = main_with_log(["--compare", str(temp_path_A), str(temp_path_B)] + addn_options)
        assert "No differences" in test

    finally:
        shutil.rmtree(temp_path_A)
        shutil.rmtree(temp_path_B)


if __name__ == "__main__":
    test_update()
