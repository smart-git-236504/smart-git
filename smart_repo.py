import ast
from contextlib import contextmanager
from typing import List, Callable, Union, Optional, Iterable

import clang
import git
from clang.cindex import Cursor, TranslationUnit

from cursor_path import CursorPath
from utils.file import file_from_blob, file_from_text


class SmartRepo(git.Repo):

    def get_cindex(self):
        if not clang.cindex.Config.library_file:
            clang.cindex.Config.set_library_file(ast.literal_eval(self.config_reader().get_value('smart',
                                                                                                 'libclangPath')))
        return clang.cindex.Index.create()

    def find_cursor(self, file_name: str, predicate: Callable[[Cursor], bool]) -> CursorPath:
        from utils.ast import search_ast
        with self.ast(self.contents(file_name), file_name) as translation_unit:
            match, = search_ast(translation_unit, file_name, predicate)
        return match

    @contextmanager
    def ast(self, file: Union[List[bytes], git.Blob], path: Optional[str]=None) -> Iterable[TranslationUnit]:
        with (file_from_blob(file) if isinstance(file, git.Blob) else file_from_text(file, path)) as file:
            parsed = self.get_cindex().parse(file.name)
            yield parsed

    def contents(self, path: str, revision: Optional[str]='HEAD') -> Optional[List[bytes]]:
        try:
            commit = self.rev_parse(revision)
        except git.BadName:
            return None
        assert isinstance(commit, git.Commit)
        tree = commit.tree
        if path not in tree:
            return None
        return tree[path].data_stream.read().splitlines(keepends=True)
