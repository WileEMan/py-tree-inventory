from time import sleep
import shutil
import logging
from pathlib import Path

from tree_inventory.actions.helpers import print_file
from t_helpers import write_text_to_file, main_with_log, parse_results

logger = logging.getLogger(__name__)


def test_general():
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
        ### With identical trees
        ###

        main_with_log(["--calculate", str(temp_path_A)] + addn_options)
        main_with_log(["--calculate", str(temp_path_B)] + addn_options)

        """
        test = main_with_log(["--compare", str(temp_path_A), str(temp_path_B)] + addn_options)
        assert "No differences" in test
        main_with_log(["--compare",
              str(temp_path_A / "Folder_C" / "Folder_C2"),
              str(temp_path_B / "Folder_C" / "Folder_C2")] + addn_options)
        assert "No differences" in test
        """

        ###
        ### Add file in Folder_C
        ###

        write_text_to_file(temp_path_B / "Folder_C" / "Created_File_1.txt", "I was created for this test.")
        main_with_log(["--calculate", str(temp_path_B)] + addn_options)
        test = main_with_log(["--compare", str(temp_path_A), str(temp_path_B)] + addn_options)
        file_mismatches, missing_A, missing_B = parse_results(test, temp_path_A, temp_path_B)
        assert file_mismatches == ["Folder_C"]
        assert len(missing_A) == 0
        assert len(missing_B) == 0

        test = main_with_log(
            ["--compare", str(temp_path_A / "Folder_C" / "Folder_C2"), str(temp_path_B / "Folder_C" / "Folder_C2")]
            + addn_options
        )
        assert "No differences" in test

        ###
        ### Add directory in Folder_C / Folder_C2
        ### (the added file is still present too)
        ###

        (temp_path_B / "Folder_C" / "Folder_C2" / "New_Directory").mkdir()
        main_with_log(["--calculate", str(temp_path_B)] + addn_options)
        test = main_with_log(["--compare", str(temp_path_A), str(temp_path_B), "--depth", "100"] + addn_options)
        file_mismatches, missing_A, missing_B = parse_results(test, temp_path_A, temp_path_B)
        assert file_mismatches == ["Folder_C"]
        assert missing_A == ["New_Directory"]
        assert len(missing_B) == 0

        ###
        ### Start comparison from within Folder_C2
        ### And also swap A and B for this test only
        ###

        test = main_with_log(
            ["--compare", str(temp_path_B / "Folder_C" / "Folder_C2"), str(temp_path_A / "Folder_C" / "Folder_C2"), "--depth", "100"]
            + addn_options
        )
        file_mismatches, missing_A, missing_B = parse_results(test, temp_path_B, temp_path_A)
        assert len(file_mismatches) == 0
        assert len(missing_A) == 0              # Missing from temp_path_B but they're swapped for this test only.
        assert missing_B == ["New_Directory"]   # Missing from temp_path_A but they're swapped for this test only.

        ###
        ### Create the file and folder in A as well, and then perform --calculate
        ### specifically on subfolder Folder_C2 only.
        ###
        ### This should update the record and the parents will be recalculated
        ### as far as Folder_C2 goes but the added file is in Folder_C and will
        ### not be recalculated.
        ###

        (temp_path_A / "Folder_C" / "Folder_C2" / "New_Directory").mkdir()
        shutil.copyfile(temp_path_B / "Folder_C" / "Created_File_1.txt", temp_path_A / "Folder_C" / "Created_File_1.txt")

        main_with_log(["--calculate", str(temp_path_A / "Folder_C" / "Folder_C2")] + addn_options)
        test = main_with_log(["--compare", str(temp_path_A), str(temp_path_B), "--depth", "100"] + addn_options)
        file_mismatches, missing_A, missing_B = parse_results(test, temp_path_A, temp_path_B)
        assert file_mismatches == ["Folder_C"]
        assert len(missing_A) == 0
        assert len(missing_B) == 0

        # Commented-out, helpful when troubleshooting...
        # print_file(temp_path_A / "tree_checksum.json")
        # print_file(temp_path_B / "tree_checksum.json")
        # print(f"file_mismatches = {file_mismatches}\nmissing_A = {missing_A}\nmissing_B = {missing_B}")

    finally:
        # shutil.rmtree(temp_path_A)
        shutil.rmtree(temp_path_B)


if __name__ == "__main__":
    test_general()
