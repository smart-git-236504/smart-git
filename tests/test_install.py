import os

import pytest
from git import Repo, SymbolicReference
import smart_git
from click.testing import CliRunner


def test_not_a_repo(empty_repo: Repo):
    assert smart_git.RepoStatus.of(empty_repo.git_dir) == smart_git.RepoStatus.not_a_repo
    assert smart_git.RepoStatus.of(empty_repo.working_dir) == smart_git.RepoStatus.not_installed


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


def test_uninstall(smart_repo, runner: CliRunner):
    runner.invoke(smart_git.uninstall, [smart_repo.working_dir])
    assert smart_git.RepoStatus.of(smart_repo.working_dir) == smart_git.RepoStatus.not_installed


def test_disable(disabled_smart_repo):
    assert smart_git.RepoStatus.of(disabled_smart_repo.working_dir) == smart_git.RepoStatus.installed_disabled

    diffs = _test_commit(disabled_smart_repo)
    assert len(diffs) == 1
    assert diffs[0].a_path != smart_git.CHANGES_FILE_NAME


def test_enable(disabled_smart_repo, runner: CliRunner):
    runner.invoke(smart_git.enable, [disabled_smart_repo.working_dir])
    assert smart_git.RepoStatus.of(disabled_smart_repo.working_dir) == smart_git.RepoStatus.installed_enabled
