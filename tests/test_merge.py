from clang.cindex import CursorKind

from changes import FileAdded, SubASTInserted, VariableRenamed
from cursor_path import CursorPath
from smart_repo import SmartRepo
from tests.conftest import commit, merge
from utils.file import as_lines
from utils.repo import get_changes


@commit({'a.c': '''
int main() {
    int a = 0;
    return a;
}
'''}, tag='initial')
@commit({'a.c': '''
int main() {
    int a = 0;
    a += 1;
    return a;
}
'''}, on='other', tag='add-line')
@commit({'a.c': '''
int main() {
    int b = 0;
    return b;
}
'''}, tag='rename')
@merge('other', tag='other-to-master')
@merge('master^1', on='other', tag='master-to-other')
def test_rename_add_merge(smart_repo: SmartRepo):
    added_line_path = CursorPath(('a.c', 'main()', (CursorKind.COMPOUND_STMT, 0),
                                  (CursorKind.COMPOUND_ASSIGNMENT_OPERATOR, 0)))
    variable_path = CursorPath(('a.c', 'main()', (CursorKind.COMPOUND_STMT, 0), (CursorKind.DECL_STMT, 0), 'a'))

    file_added = FileAdded('a.c', smart_repo.contents('a.c', 'initial'))
    line_added = SubASTInserted(smart_repo, smart_repo.contents('a.c', 'add-line'), added_line_path)
    renamed = VariableRenamed(variable_path, 'b')

    final_contents = as_lines('',
                              'int main() {',
                              '    int b = 0;',
                              '    b += 1;',
                              '    return b;',
                              '}')

    assert get_changes(smart_repo, 'other-to-master') \
        == [[file_added], [renamed], [SubASTInserted(smart_repo, final_contents, added_line_path)]]
    assert tuple(smart_repo.rev_parse('other-to-master').parents) == (smart_repo.rev_parse('rename'),
                                                                      smart_repo.rev_parse('add-line'))
    assert get_changes(smart_repo, 'master-to-other') \
        == [[file_added], [line_added], [renamed]]
    assert tuple(smart_repo.rev_parse('master-to-other').parents) == (smart_repo.rev_parse('add-line'),
                                                                      smart_repo.rev_parse('rename'))

    assert smart_repo.contents('a.c', 'other-to-master')\
        == smart_repo.contents('a.c', 'master-to-other') \
        == final_contents
