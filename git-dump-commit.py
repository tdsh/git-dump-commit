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


import argparse
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


def output_progress(count, total, name=None):
    if logger.getEffectiveLevel() == logging.DEBUG:
        if name is not None:
            sys.stdout.write('{0}\n'.format(name))
    else:
        percent = float(count) / total
        slugs = '#' * int(round(percent * 40))
        spaces = ' ' * (40 - len(slugs))
        sys.stdout.write("\r[{bar}] {percent}%".format(
            bar=slugs + spaces, percent=int(round(percent * 100))))
        sys.stdout.flush()
    return


class Commit(object):
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
            proc = subprocess.Popen(['git', 'show', commitID],
                                    cwd=os.getcwd(),
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE
                                    )
            (patch, error) = proc.communicate()
            if (error):
                logger.error('git dump-commit: {0}\n'.format(error))
                sys.exit(1)
            # Extract subject
            patch = patch.decode('utf-8')
            name = patch.split('\n')[4].strip()
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
            with open(os.path.join(self.outdir, name), "w") as f:
                f.write(patch)
            output_progress(self.pos, total, name)
            self.count += 1
            self.pos += 1
        if commitID == '':
            return
        with open(os.path.join(destdir, '.gitdump', 'DUMP_HEAD'),
                  'w') as dump_head:
            dump_head.write('%s\t%d\n' % (commitID, self.count - 1))
        output_progress(self.pos, total)
        sys.stdout.write('\n')


def key_linux_kernel(version_bytes):
    (head, tail) = version_bytes.decode('utf-8').rsplit('.', 1)
    if head == 'v2.6':
        version = '2'
        patchlevel = '06'
    else:   # v3.x or newer
        version = head.replace('v', '')
        sublevel = '00'

    if '-rc' in tail:
        (first, second) = ['{0:>02}'.format(i) for i in tail.split('-rc')]
    elif '-tree' in tail:   # workaround for 2.6.11-tree
        (first, second) = ('11', '99')
    else:
        (first, second) = ['{0:>02}'.format(i) for i in [tail, '99']]

    if version == '2':
        (sublevel, extraver) = (first, second)
    else:   # v3.x or v4.x
        (patchlevel, extraver) = (first, second)

    return int(version + patchlevel + sublevel + extraver)


def get_tag():
    """Helper to look up linux kernel
    Verify tags via "git tag" and sort them.
    """
    proc = subprocess.Popen(['git', 'tag'],
                            cwd=os.getcwd(),
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE
                            )
    (out, error) = proc.communicate()
    if error:
        return (None, error)
    out = out.split()
    res = sorted(out, key=key_linux_kernel)
    res.append(b'HEAD')
    return ([i.decode('utf-8') for i in res], error)


def get_commit_list(*versions):
    cmd_and_args = ['git', 'log', '--no-merges', '--pretty=format:%H']
    if versions:
        scope = versions[0] + '..' + versions[1]
        cmd_and_args.append(scope)
    pr = subprocess.Popen(cmd_and_args, cwd=os.getcwd(),
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    (commit_list, error) = pr.communicate()
    if error:
        logger.error('git dump-commit: {0}\n'.format(error))
        sys.exit(1)
    commit_list = commit_list.decode('utf-8').split('\n')
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


def check_head(commit_list, head_dir, latest_tag=''):
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
        f = open(os.path.join(destdir, '.gitdump', 'DUMP_HEAD'), 'r')
        last_commit = f.read()
        f.close()
        (last_commit, pos) = last_commit.split()
    except:
        shutil.rmtree(os.path.join(destdir, '.gitdump'))
        os.mkdir(os.path.join(destdir, '.gitdump'))
        shutil.rmtree(head_dir)
        os.mkdir(head_dir)
        return (commit_list, None)

    # handling HEAD when new tag is added.
    if latest_tag != '':
        try:
            with open(os.path.join(destdir, '.gitdump', 'latest_tag'), 'r') as f:
                current_tag = f.read().strip()
            if current_tag != latest_tag:
                raise Exception('New tag was added')
        except:
            shutil.rmtree(os.path.join(destdir, '.gitdump'))
            os.mkdir(os.path.join(destdir, '.gitdump'))
            shutil.rmtree(head_dir)
            os.mkdir(head_dir)
            with open(os.path.join(destdir, '.gitdump', 'latest_tag'), 'w') as f:
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

    with open(os.path.join(head_dir, patch[0]), 'r') as f:
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


def check_linux_kernel():
    """traverses linux kernel repository you're in
    and dumps all the commits of each tag.
    """
    (revs, error) = get_tag()
    if (error):
        logger.error('git dump-commit: {0}'.format(error))
        sys.exit(1)

    latest_tag = revs[-2]
    end = ''
    commit = Commit()
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
        (commit_list, patchnum) = get_commit_list(start, end)
        if len(commit_list) == 1 and commit_list[0] == '':
            # empty version
            logger.info("Skipping {0:12s} (empty)".format(end))
            continue
        commit.config(outdir, patchnum)
        (commit_list, count) = check_head(commit_list,
                                          os.path.join(destdir, 'HEAD'),
                                          latest_tag)
        if count:
            commit.update_count(count)
        if commit_list != []:
            commit.dump(commit_list)


def check_git_repo():
    """Dump all the commits of current branch.
    """
    commit = Commit()
    (commit_list, patchnum) = get_commit_list()
    commit.config(destdir, patchnum)
    (commit_list, count) = check_head(commit_list, destdir)
    if count:
        commit.update_count(count)
    if commit_list != []:
        commit.dump(commit_list)


def main():
    # Check if you're in git repo.
    proc = subprocess.Popen(['git', 'config', 'remote.origin.url'],
                            cwd=os.getcwd(),
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE
                            )
    (repo, error) = proc.communicate()
    if (error):
        logger.error('git dump-commit: {0}'.format(error))
        sys.exit(1)

    # parser arguments
    parser = argparse.ArgumentParser(description='dump all the commits')
    parser.add_argument('-v', dest='verbose', action='store_true',
                        default=False, help='vervose output')
    args = parser.parse_args()

    if args.verbose is True:
        handler.setLevel(logging.DEBUG)
        logger.setLevel(logging.DEBUG)

    logger.info("Destination directory: {0}".format(destdir))
    if not os.path.exists(destdir):
        os.mkdir(destdir)

    repo = re.sub(r'''^(git|https)://''', '', repo.decode('utf-8'))
    repo = repo.rstrip('.git\n')
    if repo in linux_kernel_repos:
        check_linux_kernel()
    else:
        check_git_repo()


if __name__ == "__main__":
    main()
