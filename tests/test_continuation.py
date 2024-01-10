from time import sleep
import shutil
import logging
import pytest
from pathlib import Path

from t_helpers import write_text_to_file, main_with_log, parse_results

logger = logging.getLogger(__name__)


@pytest.mark.parametrize("parallel", [1, 5])
def test_continuation(parallel: int):
    addn_options = ["--v", "--detail-files", "--parallel", str(parallel)]

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
        print(f"Copied tree: {resources_path}\nto: {temp_path_A}")
        shutil.copytree(resources_path, temp_path_B)
        print(f"Copied tree: {resources_path}\nto: {temp_path_B}")
        sleep(1)

        ###
        ### Test 'continuation mode' where we start from a previous calculation
        ###

        # Continuation mode will skip any folder for which the MD5 has already been
        # computed, including all subfolders.  So to test the mode, we calculate a
        # first-pass and then modify it.

        main_with_log(["--calculate", str(temp_path_A), "--new"] + addn_options)
        main_with_log(["--calculate", str(temp_path_B), "--new"] + addn_options)
        test = main_with_log(
            ["--compare", str(temp_path_A / "Folder_C" / "Folder_C2"), str(temp_path_B / "Folder_C" / "Folder_C2")]
            + addn_options
        )
        assert "No differences" in test

        # Write a file into the temp_path and run continuation on only temp_path, which should
        # cause a delta between A and B.  However, to verify that it actually ran as a continuation,
        # let's also introduce a change that should go unnoticed in continuation mode because that
        # folder is already scanned.
        continue_text = "This file should be added by continuation."
        write_text_to_file(temp_path_A / "Continuation_Folder_A" / "File_A.txt", continue_text)
        write_text_to_file(
            temp_path_A / "Folder_C" / "Ignored_file_A.txt", "This file should go unnoticed in continuation."
        )
        main_with_log(["--calculate", str(temp_path_A), "--continue"] + addn_options)

        # Calculate path B without continuation mode but also without the ignored file.
        write_text_to_file(temp_path_B / "Continuation_Folder_A" / "File_A.txt", continue_text)
        main_with_log(["--calculate", str(temp_path_B)] + addn_options)

        test = main_with_log(["--compare", str(temp_path_A), str(temp_path_B)] + addn_options)
        assert "No differences" in test

        # Finally, recompute A without continuation to make sure the 'unnoticed' file is now observed and breaks
        # the match between A and B.
        main_with_log(["--calculate", str(temp_path_A)] + addn_options)
        test = main_with_log(["--compare", str(temp_path_A), str(temp_path_B)] + addn_options)
        file_mismatches, missing_A, missing_B = parse_results(test, temp_path_A, temp_path_B)
        assert file_mismatches == ["Folder_C"]
        assert len(missing_A) == 0
        assert len(missing_B) == 0

    finally:
        shutil.rmtree(temp_path_A)
        shutil.rmtree(temp_path_B)


if __name__ == "__main__":
    test_continuation()
