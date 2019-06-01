import json
import os
from typing import List

from changes.change import Change
from changes.changes import change_from_json
from smart_repo import SmartRepo

CHANGES_FILE_NAME = '.changes'


def get_changes(repo: SmartRepo) -> List[List[Change]]:
    changes_path = os.path.join(repo.working_dir, CHANGES_FILE_NAME)
    if not os.path.isfile(changes_path):
        return []
    return [[change_from_json(repo, change_json) for change_json in json.loads(actions.partition(' ')[2])]
            for actions in open(changes_path, 'r').read().splitlines()]


