import ast
import os
from contextlib import contextmanager
from tempfile import NamedTemporaryFile
from typing import List, Callable

import clang
import git
from clang.cindex import Cursor

from cursor_path import CursorPath


class SmartRepo(git.Repo):

    def get_cindex(self):
        if not clang.cindex.Config.library_file:
            clang.cindex.Config.set_library_file(ast.literal_eval(self.config_reader().get_value('smart',
                                                                                                 'libclangPath')))
        return clang.cindex.Index.create()

    @contextmanager
    def file_from_blob(self, blob):
        with NamedTemporaryFile(suffix=os.path.splitext(blob.path)[-1]) as file:
            file.write(blob.data_stream.read())
            file.flush()
            yield file

    @contextmanager
    def file_from_text(self, text: List[bytes], path=''):
        with NamedTemporaryFile(suffix=os.path.splitext(path)[-1]) as file:
            file.write(b''.join(text))
            file.flush()
            yield file

    def find_cursor(self, file_name: str, predicate: Callable[[Cursor], bool]) -> CursorPath:
        from util import search_ast
        from repo_state import RepoState
        match, = search_ast(RepoState(self, self.head.commit.tree).ast(file_name), file_name, predicate)
        return match
