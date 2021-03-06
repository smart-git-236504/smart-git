import os
import stat
from contextlib import contextmanager
from typing import Dict, Optional

import pytest
from click.testing import CliRunner
from git.repo import Repo
import tempfile

import smart_git
from smart_repo import SmartRepo


@contextmanager
def temporary_repo(prefix: str=''):
    with tempfile.TemporaryDirectory(prefix=prefix) as repo_path, Repo.init(repo_path) as repo:
        try:
            yield repo
        finally:
            # This closes leftover git.exe processes opened by GitPython, allowing us to delete the repo directory.
            repo.git.clear_cache()

            # On Windows, the tempdir is created as read-only which prevents us from deleting it with say shutil.rmtree,
            # so we do this manual walk here (https://stackoverflow.com/a/2656408)
            for root, dirs, files in os.walk(repo_path, topdown=False):
                for name in files:
                    filename = os.path.join(root, name)
                    os.chmod(filename, stat.S_IWUSR)
                    os.remove(filename)
                for name in dirs:
                    filename = os.path.join(root, name)
                    os.chmod(filename, stat.S_IWUSR)
                    os.rmdir(filename)


@pytest.fixture
def empty_repo():
    with temporary_repo('smart-git-test-') as repo:
        yield repo


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def smart_repo(empty_repo: Repo, runner: CliRunner) -> SmartRepo:
    runner.invoke(smart_git.install, [empty_repo.working_dir, r'E:\env\LLVM\bin\libclang.dll', '--silent'])
    repo = SmartRepo(empty_repo.working_dir)
    try:
        yield repo
    finally:
        repo.git.clear_cache()
        repo.close()


@pytest.fixture
def disabled_smart_repo(smart_repo, runner: CliRunner) -> Repo:
    runner.invoke(smart_git.disable, [smart_repo.working_dir])
    return smart_repo


def commit(files: Dict[str, str], tag: Optional[str]=None, on: str='master'):
    return pytest.mark.commit(files=files, tag=tag, on=on)


def merge(what: str, tag: Optional[str]=None, on: str='master'):
    return pytest.mark.merge(what=what, tag=tag, on=on)


@pytest.hookimpl(hookwrapper=True)
def pytest_pyfunc_call(pyfuncitem):
    for name, repo in pyfuncitem.funcargs.items():
        if isinstance(repo, Repo):
            for i, marker in enumerate(reversed(list(pyfuncitem.iter_markers()))):
                marker_name = getattr(marker, 'name', None)
                if marker_name not in ('commit', 'merge'):
                    continue
                if marker.kwargs.get('applied', False):
                    continue
                else:
                    marker.kwargs['applied'] = True
                tag_name: Optional[str] = marker.kwargs['tag']
                on: str = marker.kwargs['on']
                original_branch = repo.head.reference
                if on != 'master':
                    for head in repo.heads:
                        if head.name == on:
                            branch = head
                            break
                    else:
                        branch = repo.create_head(on)
                    repo.head.reference = branch
                    repo.head.reset(index=True, working_tree=True)
                if marker_name == 'commit':
                    file_spec: Dict[str, str] = marker.kwargs['files']
                    for file_name, file_content in file_spec.items():
                        with open(os.path.join(repo.working_dir, file_name), 'wb') as file:
                            file.write(file_content.encode('utf-8'))
                    repo.index.add(file_spec.keys())
                    if smart_git.RepoStatus.of(repo.working_dir) == smart_git.RepoStatus.installed_enabled:
                        result = CliRunner().invoke(smart_git.pre_commit, [repo.working_dir])
                        if result.exception:
                            raise result.exception
                    repo.index.commit(message=repr(tag_name or f'@commit commit #{i + 1}'), skip_hooks=True)
                else:
                    what: str = marker.kwargs['what']
                    if smart_git.RepoStatus.of(repo.working_dir) == smart_git.RepoStatus.installed_enabled:
                        result = CliRunner().invoke(smart_git.merge, [repo.working_dir, what])
                        if result.exception:
                            raise result.exception
                if tag_name is not None:
                    repo.create_tag(tag_name)
                if on != 'master':
                    repo.head.reference = original_branch
                    repo.head.reset(index=True, working_tree=True)
    yield
