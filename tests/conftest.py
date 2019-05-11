import os
import stat
from typing import Dict, Optional

import pytest
from click.testing import CliRunner
from git.repo import Repo
import tempfile

import smart_git


@pytest.fixture
def empty_repo():
    with tempfile.TemporaryDirectory(prefix='smart-git-test-') as repo_path, Repo.init(repo_path) as repo:
        yield repo

        # This closes leftover git.exe processes opened by GitPython, allowing us to delete the repo directory.
        repo.git.clear_cache()

        # On Windows, the tempdir is created as read-only which prevents us from deleting it with say shutil.rmtree, so
        # we do this manual walk here (https://stackoverflow.com/a/2656408)
        for root, dirs, files in os.walk(repo_path, topdown=False):
            for name in files:
                filename = os.path.join(root, name)
                os.chmod(filename, stat.S_IWUSR)
                os.remove(filename)
            for name in dirs:
                os.rmdir(os.path.join(root, name))


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def smart_repo(empty_repo: Repo, runner: CliRunner) -> Repo:
    runner.invoke(smart_git.install, [empty_repo.working_dir, r'E:\env\LLVM\bin\libclang.dll', '--silent'])
    return empty_repo


@pytest.fixture
def disabled_smart_repo(smart_repo, runner: CliRunner) -> Repo:
    runner.invoke(smart_git.disable, [smart_repo.working_dir])
    return smart_repo


def commit(files: Dict[str, str], tag: str=None):
    return pytest.mark.commit(files=files, tag=tag)


@pytest.hookimpl(hookwrapper=True)
def pytest_pyfunc_call(pyfuncitem):
    for name, repo in pyfuncitem.funcargs.items():
        if isinstance(repo, Repo):
            for i, commit_marker in enumerate(reversed(list(pyfuncitem.iter_markers('commit')))):
                file_spec: Dict[str, str] = commit_marker.kwargs['files']
                tag_name: Optional[str] = commit_marker.kwargs['tag']
                for file_name, file_content in file_spec.items():
                    with open(os.path.join(repo.working_dir, file_name), 'w') as file:
                        file.write(file_content)
                repo.index.add(file_spec.keys())
                if smart_git.RepoStatus.of(repo.working_dir) == smart_git.RepoStatus.installed_enabled:
                    CliRunner().invoke(smart_git.pre_commit, [repo.working_dir])
                repo.index.commit(message=repr(tag_name or '@commit commit #{}'.format(i + 1)), skip_hooks=True)
                if tag_name is not None:
                    repo.create_tag(tag_name)
    yield
