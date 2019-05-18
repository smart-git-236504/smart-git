import json
import os
from collections import namedtuple
from typing import List, Callable, Iterable, Sequence

from clang.cindex import Cursor, TranslationUnit
from git import Repo

from changes.change import Change
from changes.changes import change_from_json
from cursor_path import CursorPath

CHANGES_FILE_NAME = '.changes'


def get_changes(repo: Repo) -> List[List[Change]]:
    changes_path = os.path.join(repo.working_dir, CHANGES_FILE_NAME)
    if not os.path.isfile(changes_path):
        return []
    return [[change_from_json(change_json) for change_json in json.loads(actions.partition(' ')[2])]
            for actions in open(changes_path, 'r').read().splitlines()]


def search_ast(translation_unit: TranslationUnit, file_name: str, predicate: Callable[[Cursor], bool])\
        -> Iterable[CursorPath]:
    """
    Find all cursors that satisfy a predicate.
    """

    def helper(cursor: Cursor, path: CursorPath):
        for child in cursor.get_children():
            if predicate(child):
                yield path.appended(cursor, child)
            yield from helper(child, path.appended(cursor, child))

    yield from helper(translation_unit.cursor, CursorPath((file_name, )))


def as_lines(*lines: str) -> List[bytes]:
    return [f'{line}\n'.encode('utf-8') for line in lines]


Replacement = namedtuple('Replacement', ['line', 'from_column', 'to_column', 'text'])


def apply_replacements(file_text: Sequence[bytes], replacements: Iterable[Replacement]) -> List[bytes]:
    replaced_text = list(file_text)
    replacements_by_line = {}
    for replacement in replacements:
        replacements_by_line.setdefault(replacement.line, []).append(replacement)
    for line, line_replacements in replacements_by_line.items():
        sorted_replacements = sorted(line_replacements, key=lambda replacement: replacement.from_column)
        delta = 0
        for replacement in sorted_replacements:
            prev_line = replaced_text[line]
            replaced_text[line] = prev_line[:replacement.from_column + delta] \
                                  + replacement.text.encode('utf-8') \
                                  + prev_line[replacement.to_column + delta:]
            delta += len(replacement.text) - (replacement.to_column - replacement.from_column)
    return replaced_text
