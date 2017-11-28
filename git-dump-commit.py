#!/usr/bin/env python3
#
# Copyright (C) 2013 Tadashi Abe (tadashi.abe@gmail.com)
# the BSD License: http://www.opensource.org/licenses/bsd-license.php

"""
git-dump-commit checks git branch where you're at currently
and dumps all the commits in patch format to "DUMP-COMMIT" directory.
If your repository is Linux kernel (torvalds/linux-2.6.git),
it traverses all tags and dumps commits for each kernel version.

Please run at git repository.
# git-dump-commit
or
# git dump-commit
"""


import subprocess
import os
import sys
import re
import math
import shutil
import fnmatch
import logging

logger = logging.getLogger(__name__)
handler = logging.StreamHandler()
handler.setLevel(logging.INFO)
logger.setLevel(logging.INFO)
logger.addHandler(handler)

destdir = "DUMP-COMMIT"
linux_kernel_repos = [
    'git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux',
    'git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux-2.6',
    'kernel.googlesource.com/pub/scm/linux/kernel/git/torvalds/linux',
    'github.com/torvalds/linux',
    'git@github.com:torvalds/linux'
]


def _output_progress(count, total, name=None):
    if logger.getEffectiveLevel() == logging.DEBUG:
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
    __slots__ = ('digit', 'count', 'pos', 'outdir', 'pattern1', 'pattern2',
                 'pattern3', 'pattern4', 'pattern5', 'pc_name_max')

    def __init__(self):
        self.digit = 0
        self.count = 1
        self.pos = 0
        self.outdir = ''
        self.pattern1 = re.compile(r'^\[PATCH[^]]*\]')
        self.pattern2 = re.compile(r'[^-a-z.A-Z_0-9]')
        self.pattern3 = re.compile(r'\.\.\.')
        self.pattern4 = re.compile(r'\.*$|^-|-$')
        self.pattern5 = re.compile(r'--*')
        self.pc_name_max = os.pathconf('/tmp', 'PC_NAME_MAX')

    def config(self, outdir, patchnum):
        self.digit = int(math.log10(patchnum) + 1)
        self.outdir = outdir
        self.count = 1

    def update_count(self, count):
        self.count = count

    def dump(self, commit_list):
        commitID = ''
        total = len(commit_list)
        # Run 'git show' and get the commit.
        for commitID in commit_list:
            try:
                patch = subprocess.check_output(['git', 'show', commitID], shell=False,
                                                stderr=subprocess.STDOUT)
            except subprocess.CalledProcessError as e:
                logger.error('\n\n{0}'.format(e.output.decode('utf-8')))
                sys.exit(1)
            # Extract subject
            name = patch.splitlines()[4].strip().decode('utf-8', 'ignore')
            # format the name of patch
            name = self.pattern1.sub('', name)
            name = self.pattern2.sub('-', name)
            name = self.pattern3.sub('.', name)
            name = self.pattern4.sub('', name)
            name = self.pattern5.sub('-', name)
            template = "%0" + str(self.digit) + "d-%s.patch"
            name = template % (self.count, name)
            if len(name) > self.pc_name_max:
                name = name[:self.pc_name_max - 6] + ".patch"
            with open(os.path.join(self.outdir, name), "wb") as f:
                f.write(patch)
            _output_progress(self.pos, total, name)
            self.count += 1
            self.pos += 1
        if commitID == '':
            return
        with open(os.path.join(destdir, '.gitdump', 'DUMP_HEAD'),
                  'wb') as dump_head:
            dump_head.write(b'%s\t%d\n' % (commitID, self.count - 1))
        _output_progress(self.pos, total)
        sys.stdout.write('\n')


def _key_linux_kernel(version_bytes):
    (head, tail) = version_bytes.rsplit(b'.', 1)
    if head == b'v2.6':
        version = b'2'
        patchlevel = b'06'
    else:   # v3.x or newer
        version = head.replace(b'v', b'')
        sublevel = b'00'

    if b'-rc' in tail:
        (first, second) = [b'0' + i if len(i) == 1 else i for i in tail.split(b'-rc')]
    elif b'-tree' in tail:   # workaround for 2.6.11-tree
        (first, second) = (b'11', b'99')
    else:
        (first, second) = [b'0' + i if len(i) == 1 else i for i in [tail, b'99']]

    if version == b'2':
        (sublevel, extraver) = (first, second)
    else:   # v3.x or v4.x
        (patchlevel, extraver) = (first, second)

    return int(version + patchlevel + sublevel + extraver)


def _get_tag():
    """Helper to look up linux kernel
    Verify tags via "git tag" and sort them.
    """
    error = b''
    try:
        out = subprocess.check_output(['git', 'tag'],
                                      shell=False, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as e:
        error = e.output
        return (None, error)
    out = out.split()
    res = sorted(out, key=_key_linux_kernel)
    res.append(b'HEAD')
    return ([i.decode('utf-8') for i in res], error)


def _get_commit_list(*versions):
    cmd_and_args = ['git', 'log', '--no-merges', '--pretty=format:%H']
    if versions:
        scope = versions[0] + '..' + versions[1]
        cmd_and_args.append(scope)
    try:
        commit_list = subprocess.check_output(cmd_and_args,
                                              shell=False, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as e:
        logger.error('\n\n{0}'.format(e.output.decode('utf-8')))
        sys.exit(1)
    commit_list = commit_list.splitlines()
    if len(commit_list) < 10000:
        patchnum = 1000
    else:
        patchnum = len(commit_list)
    commit_list.reverse()
    return (commit_list, patchnum)


def prepare_dir(tag):
    done = False
    quiet = True
    if tag == 'HEAD':
        return (done, quiet, '{0}/{1}'.format(destdir, tag))
    version = tag.split('-')[0]
    outdir = '{0}/{1}/{2}'.format(destdir, version, tag)
    if not os.path.exists('{0}/{1}'.format(destdir, version)):
        os.makedirs(outdir)
    elif not os.path.exists(outdir):
        os.mkdir(outdir)
    else:
        done = True
    if done is True and version == tag:
        quiet = False
    return (done, quiet, outdir)


def _check_head(commit_list, head_dir, latest_tag=b''):
    if not os.path.exists(head_dir):
        if os.path.exists(os.path.join(destdir, '.gitdump')):
            shutil.rmtree(os.path.join(destdir, '.gitdump'))
        os.mkdir(head_dir)
        os.mkdir(os.path.join(destdir, '.gitdump'))
        return (commit_list, None)
    elif not os.path.exists(os.path.join(destdir, '.gitdump')):
        if os.path.exists(head_dir):
            shutil.rmtree(head_dir)
        os.mkdir(head_dir)
        os.mkdir(os.path.join(destdir, '.gitdump'))
        return (commit_list, None)

    try:
        with open(os.path.join(destdir, '.gitdump', 'DUMP_HEAD'), 'rb') as f:
            last_commit = f.read()
        (last_commit, pos) = last_commit.split()
        pos = pos.decode('utf-8')
    except:
        shutil.rmtree(os.path.join(destdir, '.gitdump'))
        os.mkdir(os.path.join(destdir, '.gitdump'))
        shutil.rmtree(head_dir)
        os.mkdir(head_dir)
        return (commit_list, None)

    # handling HEAD when new tag is added.
    if latest_tag != b'':
        try:
            with open(os.path.join(destdir, '.gitdump', 'latest_tag'), 'rb') as f:
                current_tag = f.read().strip()
            if current_tag != latest_tag:
                raise Exception('New tag was added')
        except:
            shutil.rmtree(os.path.join(destdir, '.gitdump'))
            os.mkdir(os.path.join(destdir, '.gitdump'))
            shutil.rmtree(head_dir)
            os.mkdir(head_dir)
            with open(os.path.join(destdir, '.gitdump', 'latest_tag'), 'wb') as f:
                f.write(latest_tag)
            return (commit_list, None)

    # check for the actual patch file
    files = os.listdir(head_dir)
    patch = []
    patch = fnmatch.filter(files, '{0}-*'.format(pos))
    # Is there any better way?
    if patch == []:
        patch = fnmatch.filter(files, '0{0}-*'.format(pos))
        if patch == []:
            patch = fnmatch.filter(files, '00{0}-*'.format(pos))
            if patch == []:
                patch = fnmatch.filter(files, '000{0}-*'.format(pos))
                if patch == []:
                    patch = fnmatch.filter(files, '0000{0}-*'.format(pos))
    if patch == []:
        # Not found.
        shutil.rmtree(os.path.join(destdir, '.gitdump'))
        os.mkdir(os.path.join(destdir, '.gitdump'))
        shutil.rmtree(head_dir)
        os.mkdir(head_dir)
        return (commit_list, None)

    with open(os.path.join(head_dir, patch[0]), 'rb') as f:
        commit = f.readline().strip().split()[1]
    if commit != last_commit:
        return (commit_list, None)

    try:
        index = commit_list.index(last_commit)
    except:
        return (commit_list, None)
    pos = int(pos)
    if pos == len(commit_list):
        # No new commit exists.
        return ([], None)
    #self.count = int(pos) + 1
    count = int(pos) + 1
    return (commit_list[index + 1:], count)


def _check_linux_kernel():
    """traverses linux kernel repository you're in
    and dumps all the commits of each tag.
    """
    (revs, error) = _get_tag()
    if (error):
        logger.error('\n\n{0}'.format(error.decode('utf-8')))
        sys.exit(1)

    latest_tag = revs[-2].encode('utf-8')
    end = ''
    dump_generator = DumpGenerator()
    for revision in revs:
        start = end
        end = revision
        if start == '':
            continue
        (done, quiet, outdir) = prepare_dir(end)
        if done:
            if not quiet:
                logger.info("Skipping {0:12s} (already done)".format(end))
            continue
        logger.info("Processing {0}..{1}".format(start, end))
        (commit_list, patchnum) = _get_commit_list(start, end)
        if len(commit_list) == 1 and commit_list[0] == '':
            # empty version
            logger.info("Skipping {0:12s} (empty)".format(end))
            continue
        dump_generator.config(outdir, patchnum)
        (commit_list, count) = _check_head(commit_list,
                                           os.path.join(destdir, 'HEAD'),
                                           latest_tag)
        if count:
            dump_generator.update_count(count)
        if commit_list != []:
            dump_generator.dump(commit_list)


def _check_git_repo():
    """Dump all the commits of current branch.
    """
    dump_generator = DumpGenerator()
    (commit_list, patchnum) = _get_commit_list()
    dump_generator.config(destdir, patchnum)
    (commit_list, count) = _check_head(commit_list, destdir)
    if count:
        dump_generator.update_count(count)
    if commit_list != []:
        dump_generator.dump(commit_list)


def main():
    # Check if you're in git repo.
    try:
        repo = subprocess.check_output(['git', 'config', 'remote.origin.url'],
                                       shell=False, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as e:
        logger.error('\n\n{0}'.format(e.output.decode('utf-8')))
        sys.exit(1)

    if '-v' in sys.argv:
        # verbose output
        handler.setLevel(logging.DEBUG)
        logger.setLevel(logging.DEBUG)

    logger.info("Destination directory: {0}".format(destdir))
    if not os.path.exists(destdir):
        os.mkdir(destdir)

    repo = re.sub(r'''^(git|https)://''', '', repo.decode('utf-8'))
    repo = repo.rstrip('.git\n')
    if repo in linux_kernel_repos:
        _check_linux_kernel()
    else:
        _check_git_repo()


if __name__ == "__main__":
    main()
