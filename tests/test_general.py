from time import sleep
import shutil
import logging
from pathlib import Path

from t_helpers import print_file, write_text_to_file, main_with_log, parse_results

logger = logging.getLogger(__name__)


def test_general():
    addn_options = ["--v", "--detail-files"]

    this_dir = Path(__file__).parent
    resources_path = this_dir / "resources"
    temp_path = this_dir / "temp"
    if temp_path.exists():
        shutil.rmtree(temp_path)
    try:
        shutil.copytree(resources_path, temp_path)
        sleep(1)

        ###
        ### With identical trees
        ###

        main_with_log(["--calculate", str(resources_path)] + addn_options)
        main_with_log(["--calculate", str(temp_path)] + addn_options)

        """
        test = main_with_log(["--compare", str(resources_path), str(temp_path)] + addn_options)
        assert "No differences" in test
        main_with_log(["--compare",
              str(resources_path / "Folder_C" / "Folder_C2"),
              str(temp_path / "Folder_C" / "Folder_C2")] + addn_options)
        assert "No differences" in test
        """

        ###
        ### Add file in Folder_C
        ###

        write_text_to_file(temp_path / "Folder_C" / "Created_File_1.txt", "I was created for this test.")
        main_with_log(["--calculate", str(temp_path)] + addn_options)
        print_file(resources_path / "tree_checksum.json")
        print_file(temp_path / "tree_checksum.json")
        test = main_with_log(["--compare", str(resources_path), str(temp_path)] + addn_options)
        file_mismatches, missing_A, missing_B = parse_results(test, resources_path, temp_path)
        assert file_mismatches == ["Folder_C"]
        assert len(missing_A) == 0
        assert len(missing_B) == 0

        test = main_with_log(
            ["--compare", str(resources_path / "Folder_C" / "Folder_C2"), str(temp_path / "Folder_C" / "Folder_C2")]
            + addn_options
        )
        assert "No differences" in test

        ###
        ### Add directory in Folder_C / Folder_C2
        ### (the added file is still present too)
        ###

        (temp_path / "Folder_C" / "Folder_C2" / "New_Directory").mkdir()
        main_with_log(["--calculate", str(temp_path)] + addn_options)
        test = main_with_log(["--compare", str(resources_path), str(temp_path)] + addn_options)
        file_mismatches, missing_A, missing_B = parse_results(test, resources_path, temp_path)
        assert file_mismatches == ["Folder_C"]
        assert missing_A == ["New_Directory"]
        assert len(missing_B) == 0

        ###
        ### Start comparison from within Folder_C2
        ### And also swap A and B
        ###

        test = main_with_log(
            ["--compare", str(temp_path / "Folder_C" / "Folder_C2"), str(resources_path / "Folder_C" / "Folder_C2")]
            + addn_options
        )
        file_mismatches, missing_A, missing_B = parse_results(test, temp_path, resources_path)
        assert len(file_mismatches) == 0
        assert len(missing_A) == 0
        assert missing_B == ["New_Directory"]

    finally:
        shutil.rmtree(temp_path)


if __name__ == "__main__":
    test_general()
