import os
import stat

import pytest
from click.testing import CliRunner
from git.repo import Repo
import tempfile


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
