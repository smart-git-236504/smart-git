import os
import difflib
from io import BytesIO
from typing import Dict, Any, Type, List, Iterable

import git
import unidiff
from unidiff import Hunk, PatchedFile

from repo_state import RepoState
from smart_repo import SmartRepo
from .change import Change, Conflict


class TextualChange(Change):

    def __init__(self, file_path: str, from_line: int, to_line: int, content: List[bytes]):
        self.file_path = file_path
        self.from_line = from_line
        self.to_line = to_line
        self.content = content

    @classmethod
    def name(cls) -> str:
        return 'text'

    def apply(self, repo: git.Repo, repo_state: RepoState) -> None:
        contents = repo_state[self.file_path]
        contents[self.from_line:self.to_line] = self.content
        repo_state[self.file_path] = contents

    @property
    def removed_line_count(self):
        return self.to_line - self.from_line

    def transform(self: 'TextualChange', repo: SmartRepo, other: 'Change') -> 'TextualChange':
        if isinstance(other, TextualChange):
            if other.file_path != self.file_path:
                # A textual change in another line - we don't care.
                return self
            if self.from_line >= other.to_line:
                # Something was changed before us
                delta = len(other.content) - other.removed_line_count
                return TextualChange(self.file_path, self.from_line + delta, self.to_line + delta, self.content)
            if self.to_line <= other.from_line:
                # Something was changed after us - no need to do anything.
                return self
            # Otherwise - we're overlapping - complain
            raise Conflict
        raise Conflict

    def to_json(self) -> Dict[str, Any]:
        return dict(super(TextualChange, self).to_json(), **{'file_path': self.file_path, 'from_line': self.from_line,
                                                             'to_line': self.to_line,
                                                             'content': [line.decode('utf-8')
                                                                         for line in self.content]})

    @classmethod
    def from_json(cls: Type['TextualChange'], repo: SmartRepo, json: Dict[str, Any]) -> 'TextualChange':
        return TextualChange(file_path=json['file_path'], from_line=json['from_line'], to_line=json['to_line'],
                             content=[line.encode('utf-8') for line in json['content']])

    @classmethod
    def detect(cls: Type['TextualChange'], repo: git.Repo, diff: git.DiffIndex) -> Iterable['TextualChange']:
        for file_diff in diff:
            if file_diff.change_type != 'M':
                continue
            a = file_diff.a_blob.data_stream.read().decode('utf-8').splitlines(keepends=True)
            b = file_diff.b_blob.data_stream.read().decode('utf-8').splitlines(keepends=True)
            diff = unidiff.PatchSet.from_string(''.join(difflib.unified_diff(a, b, fromfile=file_diff.a_path,
                                                                             tofile=file_diff.b_path)))
            for hunk in diff[0]:
                assert isinstance(hunk, Hunk)
                for i, line in enumerate(hunk, hunk.source_start - 1):
                    if line.is_removed:
                        yield TextualChange(file_diff.a_path, i, i + 1, [])
                    elif line.is_added:
                        yield TextualChange(file_diff.a_path, i, i, [line.value.encode('utf-8')])
