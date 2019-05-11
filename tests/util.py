import json
import os
from typing import List

from git import Repo

from smart_git import CHANGES_FILE_NAME


def get_changes(repo: Repo) -> List[str]:
    return [json.loads(actions)
            for actions in open(os.path.join(repo.working_dir, CHANGES_FILE_NAME), 'r').read().splitlines()]
