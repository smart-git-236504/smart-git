import configparser
import os
import sys
from enum import Enum

import click
import git
import git.repo.fun


@click.group('main')
def smart_git():
    pass


repo_path_argument = click.argument('repo_path',
                                    type=click.Path(exists=True, file_okay=False, dir_okay=True, writable=True),
                                    default='.')


def path_for_git(path: str):
    return os.path.abspath(path).replace('\\', '/')


PYTHON_PATH = path_for_git(sys.executable)

ALIAS_COMMAND = '!{} {}'.format(PYTHON_PATH, path_for_git(__file__))

PRE_COMMIT_HOOK = '{python} {script} pre-commit'.format(python=PYTHON_PATH, script=path_for_git(__file__))

CHANGES_FILE_NAME = '.changes'


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


def get_repo(repo_path: str, *expected_statuses: RepoStatus):
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


@smart_git.command('status')
@repo_path_argument
def print_status(repo_path: str):
    click.echo(RepoStatus.of(repo_path).name)


@smart_git.command()
@repo_path_argument
def install(repo_path: str):
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
def uninstall(repo_path: str):
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


@smart_git.command('set-alias')
@click.option('--local', default=False, is_flag=True)
def set_alias(local):
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
def disable(repo_path: str):
    get_repo(repo_path, RepoStatus.installed_enabled)[0].config_writer().set_value('smart', 'enabled', False)


@smart_git.command()
@repo_path_argument
def enable(repo_path: str):
    get_repo(repo_path, RepoStatus.installed_disabled)[0].config_writer().set_value('smart', 'enabled', True)


@smart_git.command('pre-commit')
@repo_path_argument
def pre_commit(repo_path: str):
    repo, status = get_repo(repo_path, RepoStatus.installed_disabled, RepoStatus.installed_enabled)
    if status is RepoStatus.installed_disabled:
        return
    diff = repo.index.diff(repo.head.commit)
    with open(os.path.join(repo_path, CHANGES_FILE_NAME), 'a+') as changes_file:
        changes_file.writelines(d.a_path for d in diff)
    repo.index.add([CHANGES_FILE_NAME])


def main():
    smart_git()


if __name__ == '__main__':
    main()
