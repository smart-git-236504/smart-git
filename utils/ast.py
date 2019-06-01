from typing import Callable, Iterable

from clang.cindex import TranslationUnit, Cursor

from cursor_path import CursorPath


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