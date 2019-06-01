import difflib
import itertools
from typing import Iterable, Dict, Any, Optional, List

import git
import unidiff
from clang.cindex import Cursor, SourceLocation
from unidiff import PatchedFile, Hunk
from unidiff.patch import Line

from changes.change import Change
from cursor_path import CursorPath
from repo_state import RepoState, SingleFileRepoState
from smart_repo import SmartRepo
from utils.file import file_from_text, file_from_blob


class SubASTInserted(Change):

    def __init__(self, repo: SmartRepo, file_lines: List[bytes], ast_path: CursorPath):
        with file_from_text(file_lines, ast_path.file) as file:
            translation_unit = repo.get_cindex().parse(file.name)
        cursor = ast_path.locate(translation_unit, ast_path.file)
        parent_cursor = ast_path.drop(1).locate(translation_unit, ast_path.file)
        siblings = list(parent_cursor.get_children())
        insertion_point = siblings.index(cursor) - 1
        self.parent_path = ast_path.drop(1)
        if insertion_point == -1:
            from_location = cursor.extent.start
            self.predecessor_path = None
            if len(siblings) > 1:
                to_location = SourceLocation.from_offset(translation_unit, siblings[1].extent.start.file,
                                                         siblings[1].extent.start.offset - 1)
            else:
                to_location = cursor.extent.end
        else:
            from_location = siblings[insertion_point].extent.end
            self.predecessor_path = ast_path.drop(1).appended(parent_cursor, siblings[insertion_point])
            to_location = cursor.extent.end
        self.from_location = from_location.offset
        self.to_location = to_location.offset
        self.ast_path = ast_path
        self.file_lines = file_lines

    @classmethod
    def name(cls) -> str:
        return 'insert-sub-ast'

    def apply(self, repo: SmartRepo, repo_state: RepoState) -> None:
        ast = repo_state.ast(self.parent_path.file)
        parent_cursor = self.parent_path.locate(ast, self.parent_path.file)
        if self.predecessor_path is None:
            siblings = list(parent_cursor.get_children())
            if not siblings:
                raise NotImplementedError
            from_location = siblings[0].extent.start
        else:
            predecessor_cursor = self.predecessor_path.locate(ast, self.predecessor_path.file)
            from_location = predecessor_cursor.extent.end
        file_content = b''.join(repo_state[self.parent_path.file])
        new_content = file_content[:from_location.offset] \
                      + b''.join(self.file_lines)[self.from_location:self.to_location + 1]\
                      + file_content[from_location.offset:]
        new_lines = new_content.splitlines(keepends=True)
        repo_state[self.parent_path.file] = new_lines

    def transform(self, repo: SmartRepo, other: 'Change') -> Optional['SubASTInserted']:
        from changes import FileRenamed, FileAdded, FileDeleted, TextualChange, VariableRenamed
        if isinstance(other, FileRenamed):
            if self.ast_path.file == other.from_name:
                return SubASTInserted(repo, self.file_lines, self.ast_path.with_file(other.to_name))
            return self
        if isinstance(other, FileAdded):
            return self
        if isinstance(other, FileDeleted):
            return self
        if isinstance(other, TextualChange) and other.file_path == self.ast_path.file \
            or isinstance(other, VariableRenamed) and other.path.file == self.ast_path.file:
            state = SingleFileRepoState(repo, self.ast_path.file, self.file_lines)
            other.apply(repo, state)
            return SubASTInserted(repo, state[self.ast_path.file], self.ast_path)
        return self

    def to_json(self) -> Dict[str, Any]:
        return dict(super(SubASTInserted, self).to_json(),
                    **{'file_lines': list(line.decode('utf-8') for line in self.file_lines),
                       'ast_path': self.ast_path.to_json()})

    @classmethod
    def from_json(cls, repo: SmartRepo, json: Dict[str, Any]) -> 'SubASTInserted':
        return SubASTInserted(repo, list(line.encode('utf-8') for line in json['file_lines']),
                              CursorPath.from_json(json['ast_path']))

    def are_asts_equal(self, a: Cursor, b: Cursor):
        for a, b in itertools.zip_longest(a.get_tokens(), b.get_tokens()):
            if a is None or b is None or a.spelling != b.spelling:
                return False
        return True

    @classmethod
    def detect_ast_insertions(cls, before: Cursor, after: Cursor, ast_path: CursorPath) -> Iterable[CursorPath]:
        before_children = [hex(hash(tuple((token.kind.value, token.spelling) for token in child.get_tokens()))) + '\n'
                           for child in before.get_children()]
        after_children = [hex(hash(tuple((token.kind.value, token.spelling) for token in child.get_tokens()))) + '\n'
                          for child in after.get_children()]

        diff = unidiff.PatchSet.from_string(''.join(difflib.unified_diff(before_children, after_children, fromfile='a',
                                                                         tofile='a')))
        if not diff.modified_files:
            return
        assert len(diff.modified_files) == 1
        modified: PatchedFile = diff.modified_files[0]
        for hunk in modified:  # type: Hunk
            for i, line in enumerate(hunk):  # type: (int, Line)
                if not line.is_context and line.is_added:
                    if i != 0 and hunk[i - 1].is_removed:
                        before_child = list(before.get_children())[hunk[i - 1].source_line_no - 1]
                        after_child = list(after.get_children())[line.target_line_no - 1]
                        yield from cls.detect_ast_insertions(before_child, after_child,
                                                             ast_path.appended(after, after_child))
                    else:
                        line_no = line.target_line_no
                        yield ast_path.appended(after, list(after.get_children())[line_no - 1])

    @classmethod
    def detect(cls, repo: SmartRepo, diff: git.DiffIndex) -> Iterable['SubASTInserted']:
        for m in diff.iter_change_type('M'):
            with repo.ast(m.a_blob) as a_ast, file_from_blob(m.b_blob) as b_file:
                b_file.seek(0)
                b_ast = repo.get_cindex().parse(b_file.name)
                for inserted_path in cls.detect_ast_insertions(a_ast.cursor, b_ast.cursor, CursorPath([m.a_path])):
                    yield SubASTInserted(repo, b_file.readlines(), inserted_path)
