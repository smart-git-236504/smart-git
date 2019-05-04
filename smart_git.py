import configparser
import functools
import os
import sys
import re
from enum import Enum

from unidiff import PatchSet
import click
import git
import git.repo.fun

CHANGES_FILE_NAME = '.changes'


def path_for_git(path: str):
    return re.sub(r'^([A-Z]):', r'/\1', os.path.abspath(path).replace('\\', '/'))


PYTHON_PATH = path_for_git(sys.executable)

ALIAS_COMMAND = '!{} {}'.format(PYTHON_PATH, path_for_git(__file__))

PRE_COMMIT_HOOK = '{python} {script} pre-commit'.format(python=PYTHON_PATH, script=path_for_git(__file__))


@click.group('main')
def smart_git():
    """
    A git plugin that helps resolve merge conflicts using semantic analysis of changes on the commit level.

    Start by using set-alias to register a shortcut for accessing the plugin (via 'git smart <command>'), then install
    the plugin on the target repository using 'git smart install [<path-to-repo>]'.
    """
    pass


repo_path_argument = click.argument('repo_path',
                                    type=click.Path(exists=True, file_okay=False, dir_okay=True, writable=True),
                                    default='.')


class RepoStatus(Enum):
    """ Denotes the status of the repo w.r.t. our plugin. """

    not_a_repo = 0
    not_installed = 1
    bad_installation = 2
    installed_disabled = 3
    installed_enabled = 4

    @classmethod
    def of(cls, repo_path: str):
        if not git.repo.fun.is_git_dir(os.path.join(os.path.abspath(repo_path), '.git')):
            return RepoStatus.not_a_repo
        # noinspection PyBroadException
        try:
            repo = git.Repo(repo_path)
        except Exception:
            return RepoStatus.not_a_repo
        config_reader = repo.config_reader()
        try:
            config_value = config_reader.get_value('smart', 'enabled', None)
        except configparser.NoSectionError:
            config_value = None
        finally:
            del config_reader
        has_config_value = config_value is not None
        pre_commit_hook_path = os.path.join(repo_path, '.git', 'hooks', 'pre-commit')
        has_pre_commit_hook = os.path.isfile(pre_commit_hook_path) and PRE_COMMIT_HOOK in open(
            pre_commit_hook_path).read()
        if has_config_value != has_pre_commit_hook:
            return RepoStatus.bad_installation
        if not has_config_value:
            return RepoStatus.not_installed
        if config_value:
            return RepoStatus.installed_enabled
        return RepoStatus.installed_disabled


def get_repo(repo_path: str, *expected_statuses: RepoStatus) -> (git.Repo, RepoStatus):
    """
    Open a GitPython Repo object for the given repository path.

    :param repo_path: path to the git repository.
    :param expected_statuses: in which repo status(es) the repo at repo_path should be. An Abort is thrown if it is
                              found in a different status.
    """
    current_status = RepoStatus.of(repo_path)
    if current_status not in expected_statuses:
        click.echo(
            '{} should be {}, but is {}'.format(
                repo_path,
                'either ' + ' or '.join(status.name for status in expected_statuses)
                if len(expected_statuses) > 1
                else expected_statuses[0].name,
                current_status.name
            ),
            err=True
        )
        raise click.Abort
    return git.Repo(repo_path), current_status


def print_post_status(command):
    @functools.wraps(command)
    @click.option('--silent', '-q', is_flag=True, default=False, help="Do not print status after command execution.")
    def wrapped(*args, **kwargs):
        res = command(*args, **{k: v for k, v in kwargs.items() if k != 'silent'})
        if not kwargs['silent']:
            click.echo('[smart-git] Post status: {}'.format(RepoStatus.of(kwargs['repo_path']).name))
        return res
    return wrapped


@smart_git.command('status')
@repo_path_argument
def print_status(repo_path: str):
    """ Check the status of the repository with respect to the smart git plugin. """
    click.echo(RepoStatus.of(repo_path).name)


@smart_git.command()
@repo_path_argument
@print_post_status
def install(repo_path: str):
    """ Install the smart git plugin on the given repository and enable it. """
    repo, _ = get_repo(repo_path, RepoStatus.not_installed)
    config_writer = repo.config_writer()
    config_writer.add_section('smart')
    config_writer.set_value('smart', 'enabled', True)
    pre_commit_hook_path = os.path.join(repo_path, '.git', 'hooks', 'pre-commit')
    if not os.path.isfile(pre_commit_hook_path):
        pre_commit_hook = open(pre_commit_hook_path, 'a+')
    else:
        pre_commit_hook = open(pre_commit_hook_path, 'w')
        pre_commit_hook.write('#!/bin/sh\n')
    pre_commit_hook.write(PRE_COMMIT_HOOK)


@smart_git.command()
@repo_path_argument
@print_post_status
def uninstall(repo_path: str):
    """
    Uninstall the smart git plugin from the given repository.

    This will also remove any traces of bad installations.
    """
    get_repo(repo_path, RepoStatus.installed_disabled, RepoStatus.installed_enabled, RepoStatus.bad_installation)
    try:
        git.Git(repo_path).config('--remove-section', 'smart')
    except configparser.NoSectionError:
        pass
    pre_commit_hook_path = os.path.join(repo_path, '.git', 'hooks', 'pre-commit')
    if os.path.isfile(pre_commit_hook_path):
        lines = open(pre_commit_hook_path, 'r').read().splitlines()
        if any('smart_git' in line for line in lines):
            with open(pre_commit_hook_path, 'w') as pre_commit_hook:
                pre_commit_hook.write('\n'.join(line for line in lines if 'smart_git' not in line))


@smart_git.command()
@repo_path_argument
@click.pass_context
@print_post_status
def reinstall(ctx: click.Context, repo_path: str):
    if RepoStatus.of(repo_path) != RepoStatus.not_installed:
        ctx.invoke(uninstall, repo_path=repo_path, silent=True)
    ctx.invoke(install, repo_path=repo_path, silent=True)


@smart_git.command('set-alias')
@click.option('--local', default=False, is_flag=True)
def set_alias(local):
    """
    Set the 'git smart' git alias allowing access to the plugin commands through the git executable.

    Example - without the alias:
    python smart_git.py status
    With the alias:
    git smart status

    :param local: If passed, will only set the alias for the repository at the current directory.
    """
    try:
        git.Git('.').config('--global' if not local else '--local', 'alias.smart')
    except git.GitCommandError:
        pass
    else:
        click.echo('Alias "smart" is already set', err=True)
        raise click.Abort()
    git.Git('.').config('--global' if not local else '--local', 'alias.smart', '{}'.format(ALIAS_COMMAND))
    click.echo('You can now use git smart <command> or (git smart --help)')


@smart_git.command('clear-alias')
@click.option('--local', default=False, is_flag=True)
@click.option('-f', '--force', default=False, is_flag=True)
def clear_alias(local, force):
    """
    Clear the 'git smart' git alias.

    :param local: If passed, will only clear the alias for the repository at the current directory.
    :param force: If passed, will also clear the alias in case it is mapped to another (possibly old version or
                  user-defined) command.
    """
    try:
        current_alias = git.Git('.').config('--global' if not local else '--local', 'alias.smart')
    except git.GitCommandError:
        click.echo('Alias "smart" is not set', err=True)
        raise click.Abort()
    else:
        if current_alias != ALIAS_COMMAND and not force:
            click.echo(
                'Alias "smart" is set to a different command ({}). Pass -f to clear it anyway.'.format(current_alias)
            )
            raise click.Abort()
    git.Git('.').config('--unset', '--global' if not local else '--local', 'alias.smart')


@smart_git.command()
@repo_path_argument
@print_post_status
def disable(repo_path: str):
    """
    Disable smart git for this repository.

    This will disable any git hooks set by the plugin from running.
    """
    get_repo(repo_path, RepoStatus.installed_enabled)[0].config_writer().set_value('smart', 'enabled', False)


@smart_git.command()
@repo_path_argument
@print_post_status
def enable(repo_path: str):
    """
    Disable smart git for this repository.

    This will enable all git hooks set by the plugin.
    """
    get_repo(repo_path, RepoStatus.installed_disabled)[0].config_writer().set_value('smart', 'enabled', True)





@smart_git.command('pre-commit')
@repo_path_argument
def pre_commit(repo_path: str):
    """
    This command should not normally be used directly.

    This command will be ran before each commit, analyzing and recording the staged changes into the .changes auxiliary
    file.
    """
    repo, status = get_repo(repo_path, RepoStatus.installed_disabled, RepoStatus.installed_enabled)
    if status is RepoStatus.installed_disabled:
        return
    diff = repo.index.diff(repo.head.commit)
    if not diff:
        return
    changes_file_path = os.path.join(repo_path, CHANGES_FILE_NAME)
    if os.path.isfile(changes_file_path):
        with open(changes_file_path, 'r') as changes_file:
            prev_changes = changes_file.read()
    else:
        prev_changes = None
    with open(changes_file_path, 'a+') as changes_file:
        for d in diff:
            changes = get_changes(repo)
            changes_per_line = parse_changes(changes)
            changes_file.write('{}\n'.format(d.a_path))
            changes_file.write('\t{}\n'.format(changes_per_line))
    try:
        repo.index.add([CHANGES_FILE_NAME])
    except OSError:
        # User might have run git commit -a, which locks the index, preventing us from adding the .changes file.
        if prev_changes is None:
            os.remove(changes_file_path)
        else:
            with open(changes_file_path, 'w') as changes_file:
                changes_file.write(prev_changes)
        click.echo('[smart-git] ERROR: `git commit -a` is not currently supported with smart-git, please add the files '
                   'manually before committing (e.g. `git add .`)', err=True)
        raise click.Abort

    click.echo('[smart-git] Recorded {} change{}.'.format(len(diff), '' if len(diff) == 1 else 's'))


def get_changes(repo):
    """
    Creates the diff for a given repository. The diff will be between last commit and current
    version (in pre-commit).
    """
    commits_list = list(repo.iter_commits())
    last_commit = commits_list[0]
    changes = repo.git.diff(last_commit, repo.index.diff(None), ignore_blank_lines=True, ignore_space_at_eol=True)
    return changes


def parse_changes(changes):
    """
    This function stores all the changed lines in a dictionary where the key is
    the line number.
    """
    patch_set = PatchSet(changes)
    changes_per_line = dict()
    for patch_file in patch_set:
        for hunk in patch_file:
            for line in hunk:
                if line.is_context:
                    continue
                line_number = line.source_line_no if line.is_removed else line.target_line_no
                try:
                    changes_per_line[line_number].append(line.value)
                except KeyError:
                    changes_per_line[line_number] = [line.value]
    return changes_per_line

def main():
    smart_git()


if __name__ == '__main__':
    main()
