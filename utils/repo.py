import json
import os
from typing import List, Tuple

from changes.change import Change
from changes.changes import change_from_json
from smart_repo import SmartRepo

CHANGES_FILE_NAME = '.changes'


def decode_changes_line(repo: SmartRepo, line: bytes) -> Tuple[int, List[Change]]:
    index, _, changes_json_str = line.partition(b' ')
    return int(index), [change_from_json(repo, change_json) for change_json in json.loads(changes_json_str)]


def encode_changes_line(index: int, changes: List[Change]) -> bytes:
    return f'{index} {json.dumps([change.to_json() for change in changes])}'.encode('utf-8')


def encode_changes(changes: List[List[Change]]) -> List[bytes]:
    return [encode_changes_line(i, changes) + b'\n' for i, changes in enumerate(changes)]


def decode_changes(repo: SmartRepo, text: List[bytes]) -> List[List[Change]]:
    return [decode_changes_line(repo, line.strip())[1] for line in text]


def get_changes(repo: SmartRepo, revision: str='HEAD') -> List[List[Change]]:
    changes_file_contents = repo.contents(CHANGES_FILE_NAME, revision)
    if changes_file_contents is None:
        return []
    return decode_changes(repo, changes_file_contents)


