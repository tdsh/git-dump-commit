Dump all the commits in current Git repository
================


Contents
----

A Python script to extract and dump all the git commits from your current directory which should be a Git repository.


Usage
-----

### Run it directly

    $ git-dump-commit.py

You can run it as git sub-command if you put the file somewhere in your PATH as git-dump-commit.

    $ git dump-commit

Output files are placed under DUMP-COMMIT directory.

Or you can get verbose output with -v

    $ git dump-commit -v

### Linux kernel repository

If your remote repository is Linus's Linux kernel tree (git://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux-2.6.git), it dumps commit with sorting them out to directories named each tag name as follows.
All the commits newer than the latest version are put to HEAD.

    DUMP-COMMIT
    ├── HEAD
    ├── v2.6.11
    │   └── v2.6.11-tree
    ├── v2.6.12
    │   ├── v2.6.12
    │   ├── v2.6.12-rc2
    │   ├── v2.6.12-rc3
    │   ├── v2.6.12-rc4
    │   ├── v2.6.12-rc5
    │   └── v2.6.12-rc6
    (...)
    └── v4.1
        ├── v4.1-rc1
        ├── v4.1-rc2
        └── v4.1-rc3

Note
----

git dump-commit can do incremental dump. It tracks HEAD commit you extracted the last time. When you run git dump-commit next, it starts dump from the next commit, with the appropriate numbering of patch file.
