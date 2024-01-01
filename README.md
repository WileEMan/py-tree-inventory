# tree_inventory
The tree_inventory Python program/package provides a means of calculating/updating (--calculate) a checksum for a directory tree and subtrees.  The trees can then be compared (--compare) quickly or mirror one to the other (--update).  The tree inventory can rapidly identify duplicate folders within the tree and present them in order of the largest duplicates found (--find-duplicates).

The checksums are stored in a .json file at the root of the tree and contains checksum information for each directory in the tree as well as a checksum of all file contents within each directory.  This information facilitates rapid examination between two copies of the tree, including a detailed listing of the specific subdirectory where differences can be found.  Each filename is part of the checksum process, such that adding, removing, or renaming a file is sufficient to flag a difference between two copies of the tree.

The tree_inventory provides a command-line interface.  For information, use --help.  The package provides a number of functions that are similar to the CLI options provided.
