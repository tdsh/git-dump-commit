#!/usr/bin/env python
# -*- coding: utf-8 -*-
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

destdir = "DUMP-COMMIT"


class Commit(object):
    __slots__ = ('digit', 'count', 'outdir', 'pattern1', 'pattern2',
                 'pattern3', 'pattern4', 'pattern5', 'pc_name_max')

    def __init__(self):
        self.digit = 0
        self.count = 1
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
        # Run 'git show' and get the commit.
        for commitID in commit_list:
            proc = subprocess.Popen(['git', 'show', commitID],
                                    cwd=os.getcwd(),
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE
                                    )
            (patch, error) = proc.communicate()
            if (error):
                sys.stderr.write('git dump-commit: {0}\n'.format(error))
                sys.exit(1)
            # Extract subject
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
            print name
            with open(os.path.join(self.outdir, name), "w") as f:
                f.write(patch)
            self.count += 1
        if commitID == '':
            return
        with open(os.path.join(destdir, '.gitdump', 'DUMP_HEAD'),
                  'w') as dump_head:
            dump_head.write('%s\t%d\n' % (commitID, self.count - 1))


def cmp_linux_kernel(x, y):
    vermagic = [0, 0]
    for index, n in enumerate([x, y]):
        (head, tail) = n.rsplit('.', 1)
        if head == 'v2.6':
            version = '2'
            patchlevel = '06'
        else:   # v3.x or v4.x
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
        vermagic[index] = int(version + patchlevel + sublevel + extraver)

    if vermagic[0] > vermagic[1]:
        return 1
    if vermagic[0] < vermagic[1]:
        return -1
    else:
        return 0


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
    out = out.split()
    res = sorted(out, cmp=cmp_linux_kernel)
    res.extend(['HEAD'])
    return (res, error)


def get_commit_list(*versions):
    cmd_and_args = ['git', 'log', '--no-merges', '--pretty=format:%H']
    if versions:
        scope = versions[0] + '..' + versions[1]
        cmd_and_args.append(scope)
    pr = subprocess.Popen(cmd_and_args, cwd=os.getcwd(),
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    (commit_list, error) = pr.communicate()
    if error:
        sys.stderr.write('git dump-commit: {0}\n'.format(error))
        sys.exit(1)
    commit_list = commit_list.split('\n')
    if len(commit_list) < 10000:
        patchnum = 1000
    else:
        patchnum = len(commit_list)
    commit_list.reverse()
    return (commit_list, patchnum)


def prepare_dir(tag):
    done = False
    if tag == 'HEAD':
        return (done, '{0}/{1}'.format(destdir, tag))
    version = tag.split('-')[0]
    outdir = '{0}/{1}/{2}'.format(destdir, version, tag)
    if not os.path.exists('{0}/{1}'.format(destdir, version)):
        os.makedirs(outdir)
    elif not os.path.exists(outdir):
        os.mkdir(outdir)
    else:
        done = True
    return (done, outdir)


def check_head(commit_list, head_dir):
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
        sys.stderr.write('git dump-commit: {0}\n'.format(error))
        sys.exit(1)

    end = ''
    commit = Commit()
    for revision in revs:
        start = end
        end = revision
        if start == '':
            continue
        (done, outdir) = prepare_dir(end)
        if done:
            print("Skipping {0:12s} (directory already exists)".format(end))
            continue
        print "Processing %s..%s" % (start, end)
        (commit_list, patchnum) = get_commit_list(start, end)
        commit.config(outdir, patchnum)
        (commit_list, count) = check_head(commit_list,
                                          os.path.join(destdir, 'HEAD'))
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
    proc = subprocess.Popen(['git', 'remote', '-v'],
                            cwd=os.getcwd(),
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE
                            )
    (repo, error) = proc.communicate()
    if (error):
        sys.stderr.write('git dump-commit: {0}\n'.format(error))
        sys.exit(1)

    print "Destination directory: %s" % destdir
    if not os.path.exists(destdir):
        os.mkdir(destdir)

    if 'torvalds/linux-2.6.git (fetch)' in repo or \
       'github.com/mirrors/linux.git (fetch)' in repo:
        check_linux_kernel()
    else:
        check_git_repo()


if __name__ == "__main__":
    main()
