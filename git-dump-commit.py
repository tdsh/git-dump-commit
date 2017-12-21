#!/usr/bin/env python3
#
# The MIT License (MIT)
#
# Copyright (C) 2013-2017 Tadashi Abe (tadashi.abe@gmail.com)
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# “Software”), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
# CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
# TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
#

"""
git-dump-commit checks git branch where you're at currently
and dumps all the commits in patch format to "DUMP-COMMIT" directory.

Please run at git repository.
# git-dump-commit -a
or it can put each commit file to directory of tag name.
# git dump-commit
"""


import argparse
import fnmatch
import logging
import os
import re
import shutil
import subprocess
import sys

LOGGER = logging.getLogger(__name__)
CH = logging.StreamHandler()
CH.setLevel(logging.INFO)
LOGGER.setLevel(logging.INFO)
LOGGER.addHandler(CH)

DEST_DIR = "DUMP-COMMIT"


def _output_progress(count, total, name=None):
    """Outputs progress bar, percentage and the number of files dumped.

    Args:
        count: an integer of the number of commit dune with dump.
        total: an integer of the total number of commit.
        name: a str of the name of patch file.
    """
    if LOGGER.getEffectiveLevel() == logging.DEBUG:
        if name is not None:
            sys.stdout.write('{0}\n'.format(name))
    else:
        percent = float(count) / total
        slugs = '#' * int(round(percent * 40))
        spaces = ' ' * (40 - len(slugs))
        sys.stdout.write("\r[{bar}] {percent:>3}% ({count:>{digit}} / {total})".format(
            bar=slugs + spaces, percent=int(round(percent * 100)),
            count=count, total=total, digit=len(str(total))))
        sys.stdout.flush()
    return


class DumpGenerator(object):
    """class which holds various dump status and generated dump file actually.

    Attributes:
        digit: an integer indicating number of digits in the range of commits.
        count: an integer indicating current number of commit.
        outdir: a str of output directory.
        pattern: a list of a re pattern object to be used to format dump file name.
        pc_name_max: an integer indicating the max length of path name.
        revision_range: a list of str indicating commit range (start and end).
        latest_commit_id: a bytes of the latest commit ID.
        latest_tag: a str of the latest tag.
    """
    __slots__ = ('digit', 'offset', 'outdir', 'pattern', 'pc_name_max', 'revision_range',
                 'latest_commit_id', 'latest_tag')

    def __init__(self, head_dir):
        """Inits DumpGenerator."""
        self.digit = 0
        self.offset = 1
        self.outdir = ''
        self.pattern = [re.compile(r'^\[PATCH[^]]*\]'), re.compile(r'[^-a-z.A-Z_0-9]'),
                        re.compile(r'\.\.\.'), re.compile(r'\.*$|^-|-$'), re.compile(r'--*')]
        self.pc_name_max = os.pathconf('/tmp', 'PC_NAME_MAX')
        self.revision_range = []
        self.latest_commit_id = b''
        self.latest_tag = ''
        if not os.path.exists(head_dir) or not os.path.exists(os.path.join(DEST_DIR, '.gitdump')) \
                or not os.path.exists(os.path.join(DEST_DIR, '.gitdump', 'DUMP_HEAD')):
            _init_meta_dir(head_dir)

    def check_new_tag(self, latest_tag, head_dir):
        """Checks if new tag is added."""
        self.latest_tag = latest_tag
        if not os.path.exists(os.path.join(DEST_DIR, '.gitdump', 'LATEST_TAG')):
            _init_meta_dir(head_dir)
        else:
            with open(os.path.join(DEST_DIR, '.gitdump', 'LATEST_TAG')) as f:
                current = f.read()
            if self.latest_tag != current:
                _init_meta_dir(head_dir)

    def config(self, outdir, patchnum, revision_range=None):
        """Changes digit and outdir. And resets offset."""
        if patchnum < 1000:
            patchnum = 1000
        self.digit = len(str(patchnum))
        self.outdir = outdir
        self.offset = 1
        self.revision_range = revision_range

    def update_offset(self, offset):
        self.offset = offset

    def dump(self, commit_list):
        """Dumps each commit to file actually."""
        commit_id = ''
        pos = 0
        total = len(commit_list)
        # Run 'git show' and get the commit.
        for commit_id in commit_list:
            try:
                patch = subprocess.check_output(['git', 'show', commit_id], shell=False,
                                                stderr=subprocess.STDOUT)
            except subprocess.CalledProcessError as error:
                LOGGER.error('\n\n%s', error.output.decode('utf-8'))
                sys.exit(1)
            # Extract subject
            name = patch.splitlines()[4].strip().decode('utf-8', 'ignore')
            # format the name of patch
            name = self.pattern[0].sub('', name)
            name = self.pattern[1].sub('-', name)
            name = self.pattern[2].sub('.', name)
            name = self.pattern[3].sub('', name)
            name = self.pattern[4].sub('-', name)
            template = "%0" + str(self.digit) + "d-%s.patch"
            name = template % (self.offset, name)
            if len(name) > self.pc_name_max:
                name = name[:self.pc_name_max - 6] + ".patch"
            with open(os.path.join(self.outdir, name), "wb") as dump_file:
                dump_file.write(patch)
            self.offset += 1
            pos += 1
            _output_progress(pos, total, name)
        self.latest_commit_id = commit_id
        _output_progress(pos, total)
        sys.stdout.write('\n')

    def write_metadata(self):
        """Writes out metadata."""
        if self.latest_commit_id != b'':
            with open(os.path.join(DEST_DIR, '.gitdump', 'DUMP_HEAD'), 'wb') as dump_head:
                dump_head.write(b'%s\t%d\n' % (self.latest_commit_id, self.offset - 1))
        if self.latest_tag != '':
            with open(os.path.join(DEST_DIR, '.gitdump', 'LATEST_TAG'), 'w') as tag_file:
                tag_file.write(self.latest_tag)


def _get_tag(tag_name):
    """Helper function to look up linux kernel.

    This verifies tags via "git tag" by taggerdate order.

    Args:
        tag_name: a str representing pattern of tag name. This is passed to
        "git tag".
    Returns:
        A tuple of
        - a list of str representing tag name.
    Raises:
        subprocess.CalledProcessError: an erro occurred in "git tag" command.
    """
    args = ['git', 'tag', '--sort=taggerdate']
    if tag_name != '':
        args.extend(['-l', tag_name])
    try:
        out = subprocess.check_output(args, shell=False, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError:
        raise
    out = out.split()
    if tag_name == '':
        out.append(b'HEAD')
    return [i.decode('utf-8') for i in out]


def _get_commit_list(start='', end=''):
    """Gets list of commit ID and the length.

    Args:
        start: str representing tag name which starts commit.
        end: str representing tag name which ends commit.
    Returns:
        commit_list: a list of bytes representing commit ID.
    Raises:
        subprocess.CalledProcessError: an erro occurred in "git log" command.
    """
    cmd_and_args = ['git', 'log', '--no-merges', '--pretty=format:%H']
    if start or end:
        scope = start + '..' + end
        cmd_and_args.append(scope)
    try:
        commit_list = subprocess.check_output(cmd_and_args,
                                              shell=False, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError:
        raise
    commit_list = commit_list.splitlines()
    commit_list.reverse()
    return commit_list


def _setup_dump_dir(tag):
    """Creates directory whose name is tag.

    Args:
        tag: str representing tag name.
    Returns:
        A tuple of the following 3 elements.
        - bool. True if the directory exists already.
        - bool. True if tag is RC version.
        - str of directory name
    """
    done = False
    rc_release = True
    if tag == 'HEAD':
        return (done, rc_release, '{0}/{1}'.format(DEST_DIR, tag))
    # If tag contains 'RC', 'rc', 'PRE', 'pre', 'BETA' or 'beta', the tag can
    # be thought as release candidate for primary version.
    # Create directory named tag under primary version directory in that case.
    suffixes = ['rc', 'pre', 'beta', None]
    for suffix_nom in suffixes:
        if suffix_nom is None or suffix_nom in tag.lower():
            break
    suffix = suffix_nom
    version = tag.lower().split(suffix)[0]
    if version[-1] in ['-', '_', '.']:
        version = version[:-1]
    if version != tag:
        outdir = '{0}/{1}/{2}'.format(DEST_DIR, version, tag)
    else:
        outdir = '{0}/{1}'.format(DEST_DIR, version)
    if not os.path.exists('{0}/{1}'.format(DEST_DIR, version)):
        os.makedirs(outdir)
    elif not os.path.exists(outdir):
        os.mkdir(outdir)
    else:
        done = True
    if done is True and version == tag:
        rc_release = False
    return (done, rc_release, outdir)


def _init_meta_dir(head_dir):
    """Initializes HEAD directory and .gitdump where meta file is located at.
    """
    shutil.rmtree(head_dir, ignore_errors=True)
    shutil.rmtree(os.path.join(DEST_DIR, '.gitdump'), ignore_errors=True)
    os.mkdir(head_dir)
    os.mkdir(os.path.join(DEST_DIR, '.gitdump'))
    return


def _fast_forward_commit_list(commit_list, head_dir):
    """Checks commit ID dumped most recently and fast-forwards commit_list
    to avoid unnecessary dump.

    Args:
        commit_list: list of bytes representing commit ID.
        head_dir: A string of HEAD directory.
    Returns:
        A tuple of
        - a list of bytes of commit ID with fast-forwarded if applicable.
        - an integer representing the next offset.
    Raises:
        OSError: an error occurred accessing metadata or patch files.
        ValueError: an error occurred looking up commit in the list.
    """
    # If head_dir or DUMP-COMMIT/.gitdump or DUMP-COMMIT/.gitdump/DUMP_HEAD doesn't exist,
    # it can't track current status. Do full dump.
    if not os.path.exists(head_dir) or not os.path.exists(os.path.join(DEST_DIR, '.gitdump')) \
       or not os.path.exists(os.path.join(DEST_DIR, '.gitdump', 'DUMP_HEAD')):
        _init_meta_dir(head_dir)
        raise OSError

    try:
        with open(os.path.join(DEST_DIR, '.gitdump', 'DUMP_HEAD'), 'rb') as dump_head:
            last_commit, offset = dump_head.read().split()
        offset = int(offset)
    except OSError:
        _init_meta_dir(head_dir)
        raise

    # Find the latest commit file in HEAD.
    files = os.listdir(head_dir)
    patch = []
    for i in range(5):
        patch = fnmatch.filter(files, '0' * i + '{0}-*'.format(offset))
        if patch != []:
            break
    if patch == []:
        # Not found. Give up.
        _init_meta_dir(head_dir)
        raise OSError

    with open(os.path.join(head_dir, patch[0]), 'rb') as last_commit_file:
        commit_id = last_commit_file.readline().strip().split()[1]
    if commit_id != last_commit:
        # Mismatch of last commit ID in DUMP-COMMIT/.gitdump/DUMP_HEAD.
        raise OSError

    # If last commit ID is same, it's possible that the other commits are
    # merged before the last commit because it's chronological order.
    # Dump again also in that case.
    list_len = len(commit_list)
    if offset != list_len:
        _init_meta_dir(head_dir)
        raise OSError

    try:
        index = commit_list.index(last_commit)
    except ValueError:
        raise
    if offset == len(commit_list):
        # No new commit exists.
        return ([], None)
    # Fast-forward commit_list and offset.
    return (commit_list[index + 1:], offset + 1)


def _dump_per_tag(tag_name):
    """Dumps commits into directory named each tag.

    It traverses repository you're in and dumps all the commits of each tag.
    """
    try:
        revs = _get_tag(tag_name)
    except subprocess.CalledProcessError as err:
        LOGGER.error('\n\n%s', err.output.decode('utf-8'))
        sys.exit(1)

    # Even without "-a", put all the dumps just in the directory if no tag is set.
    revs_len = len(revs)
    if revs_len == 0 or (revs_len == 1 and revs[0] == 'HEAD'):
        _dump_in_lump()
        sys.exit(0)

    end = ''
    dump_generator = DumpGenerator(os.path.join(DEST_DIR, 'HEAD'))
    dump_generator.check_new_tag(revs[-2], os.path.join(DEST_DIR, 'HEAD'))
    for revision in revs:
        start = end
        end = revision
        if start == '':
            continue
        (done, rc_release, outdir) = _setup_dump_dir(end)
        if done:
            if not rc_release:
                LOGGER.info("Skipping {0:12s} (already done)".format(end))
            continue
        try:
            commit_list = _get_commit_list(start, end)
        except subprocess.CalledProcessError as err:
            LOGGER.error('\n\n%s', err.output.decode('utf-8'))
            sys.exit(1)
        if len(commit_list) == 1 and commit_list[0] == '':
            # empty version
            LOGGER.info("Skipping {0:12s} (empty)".format(end))
            continue
        dump_generator.config(outdir, len(commit_list), [start, end])
        try:
            (commit_list, offset) = _fast_forward_commit_list(commit_list,
                                                              os.path.join(DEST_DIR, 'HEAD'))
        except (OSError, ValueError):
            offset = None
        if offset:
            dump_generator.update_offset(offset)
        if commit_list != []:
            LOGGER.info("Processing %s..%s", start, end)
            dump_generator.dump(commit_list)
        else:
            LOGGER.info("Processing {0:10s} (up to date)".format(end))
    dump_generator.write_metadata()


def _dump_in_lump():
    """Dump all the commits of current branch into one directory.
    """
    dump_generator = DumpGenerator(DEST_DIR)
    try:
        commit_list = _get_commit_list()
    except subprocess.CalledProcessError as err:
        LOGGER.error('\n\n%s', err.output.decode('utf-8'))
        sys.exit(1)
    dump_generator.config(DEST_DIR, len(commit_list))
    try:
        (commit_list, offset) = _fast_forward_commit_list(commit_list, DEST_DIR)
    except (OSError, ValueError):
        offset = None
    if offset:
        dump_generator.update_offset(offset)
    if commit_list != []:
        dump_generator.dump(commit_list)
        dump_generator.write_metadata()


if __name__ == "__main__":
    # Check if you're in git repo.
    ret = subprocess.call(['git', 'status', '-uno'], shell=False,
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if ret != 0:
        sys.exit(1)

    parser = argparse.ArgumentParser('git-dump-commit')
    parser.add_argument('-a', '--all', action='store_true', default=False,
                        help='Puts all the dumps into the one directory.')
    parser.add_argument('-v', '--verbose', action='store_true', default=False,
                        help='Verbose output.')
    parser.add_argument('tag_name', action='store', nargs='?', default='', type=str,
                        help='Tag which matches the pattern(s). '
                        'The pattern is a shell wildcard (matched using fnmatch). '
                        "This option doesn't mean anything if -a option is used"
                        'at the same time.',
                        metavar=None)
    args = parser.parse_args()

    if args.verbose is True:
        CH.setLevel(logging.DEBUG)
        LOGGER.setLevel(logging.DEBUG)

    LOGGER.info("Destination directory: %s", DEST_DIR)
    if not os.path.exists(DEST_DIR):
        os.mkdir(DEST_DIR)

    if args.all is True:
        _dump_in_lump()
    else:
        _dump_per_tag(args.tag_name)
