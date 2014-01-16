Dump all the commits in current Git repository
================


Contents
----

A Python script to extract and dump all the git commits
from your current directory which should be a Git repository.


Usage
-----

### Run it directly

    % git-dump-commit

You can run it as git sub-command if you put the file somewhere
in your PATH.

	% git dump-commit

Output files are placed under DUMP-COMMIT directory.

### Linux kernel repository

If your remote repository is Linus's kernel tree,
it dumps commit with sorting them out to directories
named each tag name (Like "v3.12-rc8").

	DUMP-COMMIT/
	|-- v2.6.11-tree
	|-- v2.6.12
	(...)
	|-- v3.13-rc6
	|-- v3.13-rc7
