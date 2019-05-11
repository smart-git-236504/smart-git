import os

import pytest
from git import Repo, SymbolicReference
import smart_git
from click.testing import CliRunner


def test_not_a_repo(empty_repo: Repo):
    assert smart_git.RepoStatus.of(empty_repo.git_dir) == smart_git.RepoStatus.not_a_repo
    assert smart_git.RepoStatus.of(empty_repo.working_dir) == smart_git.RepoStatus.not_installed


@pytest.fixture
def installed_empty_repo(empty_repo: Repo, runner: CliRunner) -> Repo:
    runner.invoke(smart_git.install, [empty_repo.working_dir, '--silent'])
    return empty_repo


@pytest.fixture
def smart_repo(installed_empty_repo: Repo, runner: CliRunner) -> Repo:
    installed_empty_repo.git.commit(message='"Initial commit"', allow_empty=True)
    return installed_empty_repo


def _test_commit(repo: Repo):
    test_file_path = 'a'
    with open(os.path.join(repo.working_dir, test_file_path), 'w') as test_file:
        test_file.write('test')
    repo.index.add([test_file_path])
    repo.git.commit(message='"Test commit"')
    if SymbolicReference(repo, 'HEAD^').is_valid():
        return repo.head.commit.diff('HEAD^')
    return repo.head.commit.diff(smart_git.EMPTY_COMMIT_SHA)


def test_install(smart_repo: Repo):
    assert smart_git.RepoStatus.of(smart_repo.working_dir) == smart_git.RepoStatus.installed_enabled
    diffs = _test_commit(smart_repo)
    assert len(diffs) == 2
    assert any(d.a_path == d.b_path == smart_git.CHANGES_FILE_NAME for d in diffs)


def test_uninstall(installed_empty_repo: Repo, runner: CliRunner):
    runner.invoke(smart_git.uninstall, [installed_empty_repo.working_dir])
    assert smart_git.RepoStatus.of(installed_empty_repo.working_dir) == smart_git.RepoStatus.not_installed


@pytest.fixture
def disabled_empty_repo(installed_empty_repo: Repo, runner: CliRunner) -> Repo:
    runner.invoke(smart_git.disable, [installed_empty_repo.working_dir])
    return installed_empty_repo


def test_disable(disabled_empty_repo: Repo):
    assert smart_git.RepoStatus.of(disabled_empty_repo.working_dir) == smart_git.RepoStatus.installed_disabled

    diffs = _test_commit(disabled_empty_repo)
    assert len(diffs) == 1
    assert diffs[0].a_path != smart_git.CHANGES_FILE_NAME


def test_enable(disabled_empty_repo: Repo, runner: CliRunner):
    runner.invoke(smart_git.enable, [disabled_empty_repo.working_dir])
    assert smart_git.RepoStatus.of(disabled_empty_repo.working_dir) == smart_git.RepoStatus.installed_enabled
