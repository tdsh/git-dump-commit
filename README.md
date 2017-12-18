Dump all the commits in current Git repository
================


Contents
----

git-dump-commit is a git subcommand to to extract and dump all the git commits from your current directory. This can be run as `git dump-commit` by the original script `git-dump-commit.py` at somewhere in your PATH. This is written by Python and supports Python 3 only.

Usage
-----

1. Put `git-dump-commit.py` at somewhere in your PATH.

  ```shell
  # mv git-dump-commit.py /usr/local/bin
  ```

1. Run `git dump-commit` at directory of git local repo. It has several options.

  ```shell
  $ git dump-commit
  ```

Without any option or argument, `git dump-commit` dumps all the commits with sorting them out to directories named each tag name. For example, here's the output directory structure if your remote repository is Linus's Linux kernel tree (https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git). All the commits newer than the latest tag are put to HEAD directory.

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

It has several options. See the following Options or run `git dump-commit -h`.

Options
-------

With `-a` option, it puts all the commit dumps into the one directory.

  ```shell
  $ git dump-commit -a
  ```

You can get verbose output with `-v`.

  ```shell
  $ git dump-commit -v
  ```

If you specify a pattern of tag name, it dumps only commits contained in the specified tag.
The pattern is a shell wildcard (matched using fnmatch). For example, when `v4.14*` is given in the Linux kernel git repo as follows, only the commits between v4.14-rc1 and v4.14.

  ```shell
  $ git dump-commit v4.14*
  ```

Note
----

* It's made by Python 3. You need to install Python 3.
* git dump-commit can do incremental dump. It tracks HEAD commit you extracted the last time. When you run git dump-commit next, it starts dump from the next commit, with the appropriate numbering of patch file.

License
----

Under MIT License: https://tdsh.mit-license.org/
