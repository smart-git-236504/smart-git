from typing import Tuple, Union, List, Optional, Sequence

from clang.cindex import Cursor, TranslationUnit, CursorKind

CursorPathElement = Union[str, Tuple[CursorKind, int]]


class CursorPath:
    """
    A type that extracts information that identifies a cursor within the AST, and which can be used to locate that same
    cursor in other ASTs.

    For example, the cursor path of the variable 'a' within the following code:

    file.c:
    int main() {
        int x;
        int a;
    }

    Might be: file.c:main().COMPOUND_STMT#0.DECL_STMT#1.a
    """

    def __init__(self, elements: Sequence[Union[Cursor, CursorPathElement]] = ()):
        if len(elements) == 0:
            self._path: Tuple[CursorPathElement, ...] = ()
        elif isinstance(elements[0], Cursor):
            self._path: Tuple[CursorPathElement, ...] = (elements[0].displayname, )
            for parent, child in zip(elements, elements[1:]):
                self._path += (self.element_from_cursor(parent, child), )
        else:
            self._path: Tuple[CursorPathElement, ...] = tuple(elements)

    def appended(self, parent: Union[Cursor, str], child: Optional[Cursor]=None):
        if isinstance(parent, str):
            return CursorPath(self._path + (parent, ))
        assert isinstance(parent, Cursor) and isinstance(child, Cursor)
        return CursorPath(self._path + (self.element_from_cursor(parent, child), ))

    def drop(self, n: int):
        return CursorPath(self._path[:len(self._path) - n])

    @staticmethod
    def element_from_cursor(parent: Cursor, child: Cursor) -> CursorPathElement:
        if child.displayname:
            return child.displayname
        children_of_kind = [sibling for sibling in parent.get_children() if sibling.kind == child.kind]
        return child.kind, children_of_kind.index(child)

    @property
    def file(self):
        return self._path[0]

    @staticmethod
    def match_element(parent: Cursor, element: CursorPathElement):
        if isinstance(element, str):
            for child in parent.get_children():
                if child.displayname == element:
                    yield child
        else:
            children_of_kind = [child for child in parent.get_children() if child.kind == element[0]]
            if len(children_of_kind) > element[1]:
                yield children_of_kind[element[1]]

    def locate(self, translation_unit: TranslationUnit, file_name: str) -> Cursor:
        if file_name != self.file:
            raise KeyError(f'This path points to file {self.file}, given translation unit is '
                           f'{translation_unit.spelling}')
        current: Cursor = translation_unit.cursor
        found: Tuple[str, ...] = (self.file, )
        path = self._path[1:]
        while path:
            candidates = list(self.match_element(current, path[0]))
            if len(candidates) == 0:
                raise KeyError(f'Could not find cursor named `{path[0]}` in {".".join(found)}')
            if len(candidates) != 1:
                raise KeyError(f'Multiple children matching `{path[0]}` in {".".join(found)}')
            current = candidates[0]
            path = path[1:]
        return current

    def __repr__(self):
        return f'{self.file}:' + '.'.join(element if isinstance(element, str) else f'{element[0].name}#{element[1]}'
                                          for element in self._path[1:])

    def __eq__(self, other):
        return isinstance(other, CursorPath) and other.path == self.path

    def __hash__(self):
        return hash(self._path)

    def to_json(self) -> List:
        return [element if isinstance(element, str) else [element[0].name, element[1]] for element in self._path]

    @classmethod
    def from_json(cls, json: List) -> 'CursorPath':
        return cls(tuple(element_json if isinstance(element_json, str) else (getattr(CursorKind, element_json[0]),
                                                                             element_json[1])
                         for element_json in json))

    @property
    def path(self) -> Tuple[CursorPathElement, ...]:
        return self._path

    def with_file(self, file: str) -> 'CursorPath':
        return CursorPath((file, ) + self._path[1:])