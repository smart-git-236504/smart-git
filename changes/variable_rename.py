from typing import Iterable, Dict, Any, Optional, Type

import git
from clang.cindex import CursorKind, SourceRange, SourceLocation

from changes.change import Change, T
from cursor_path import CursorPath
from renaming_detector import RenamingDetector
from repo_state import RepoState
from smart_repo import SmartRepo
from utils.ast import search_ast
from utils.file import apply_replacements, file_from_blob, file_from_text, Replacement


class VariableRenamed(Change):

    def __init__(self, path: CursorPath, new_name: str):
        self.path = path
        self.new_name = new_name

    @classmethod
    def name(cls) -> str:
        return 'variable-renamed'

    def apply(self, repo: SmartRepo, repo_state: RepoState) -> None:
        file_text = repo_state[self.path.file]
        with file_from_text(file_text, self.path.file) as file:
            translation_unit = repo.get_cindex().parse(file.name)
            variable = self.path.locate(translation_unit, self.path.file)
            usages = search_ast(translation_unit, self.path.file,
                                lambda cursor: cursor.kind == CursorKind.DECL_REF_EXPR
                                               and cursor.get_definition() == variable)
            replacements = [Replacement(variable.location.line - 1, variable.location.column - 1,
                                        variable.location.column + len(variable.spelling) - 1, self.new_name)]
            for usage_path in usages:
                usage = usage_path.locate(translation_unit, self.path.file)
                range: SourceRange = usage.extent
                start: SourceLocation = range.start
                end: SourceLocation = range.end
                assert start.line == end.line
                assert file_text[start.line - 1][start.column - 1:end.column - 1] == variable.spelling.encode('utf-8')
                replacements.append(Replacement(start.line - 1, start.column - 1, end.column - 1, self.new_name))
            file_text = apply_replacements(file_text, replacements)
        repo_state[self.path.file] = file_text

    def transform(self: T, repo: git.Repo, other: 'Change') -> Optional[T]:
        pass

    def to_json(self) -> Dict[str, Any]:
        return dict(super(VariableRenamed, self).to_json(), **{'path': self.path.to_json(), 'new_name': self.new_name})

    @classmethod
    def from_json(cls, json: Dict[str, Any]) -> 'VariableRenamed':
        return cls(path=CursorPath.from_json(json['path']), new_name=json['new_name'])

    @classmethod
    def detect(cls: Type['VariableRenamed'], repo: SmartRepo, diff: git.DiffIndex) -> Iterable['VariableRenamed']:
        for m in diff.iter_change_type('M'):
            with file_from_blob(m.a_blob) as a, file_from_blob(m.b_blob) as b:
                for renamed, new_name in RenamingDetector(repo.get_cindex()).get_renamed_variables(m.a_path, a.name,
                                                                                                   b.name).items():
                    yield VariableRenamed(renamed, new_name)
