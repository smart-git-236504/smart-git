from clang.cindex import CursorKind

from changes import SubASTInserted, FileAdded
from cursor_path import CursorPath
from smart_repo import SmartRepo
from tests.conftest import commit
from utils.file import as_lines
from utils.repo import get_changes


@commit({'a.c': '''
int main() {

}
'''})
@commit({'a.c': '''
int foo() { }
int main() {

}
'''})
def test_insert_function(smart_repo: SmartRepo):
    assert get_changes(smart_repo) == [[FileAdded('a.c', as_lines('',
                                                                  'int main() {',
                                                                  '',
                                                                  '}'))],
                                       [SubASTInserted(smart_repo, as_lines('',
                                                                    'int foo() { }',
                                                                    'int main() {',
                                                                    '',
                                                                    '}'), CursorPath(('a.c', 'foo()')))]]


@commit({'a.c': '''
int main() {
    if (1) {
        return 1;
    }
}
'''})
@commit({'a.c': '''
int main() {
    if (1) {
        printf("hello");
        return 1;
    }
}
'''})
@commit({'a.c': '''
int main() {
    if (1) {
        printf("hello");
    return 0;
        return 1;
    }
}
'''})
def test_insert_statement(smart_repo: SmartRepo):
    assert get_changes(smart_repo) == [[FileAdded('a.c', as_lines('',
                                                                  'int main() {',
                                                                  '    if (1) {',
                                                                  '        return 1;',
                                                                  '    }',
                                                                  '}'))],
                                       [SubASTInserted(smart_repo, as_lines('',
                                                                    'int main() {',
                                                                    '    if (1) {',
                                                                    '        printf("hello");',
                                                                    '        return 1;',
                                                                    '    }',
                                                                            '}'), CursorPath(('a.c', 'main()',
                                                                                      (CursorKind.COMPOUND_STMT, 0),
                                                                                      (CursorKind.IF_STMT, 0),
                                                                                      (CursorKind.COMPOUND_STMT, 0),
                                                                                      'printf')))],
                                       [SubASTInserted(smart_repo, as_lines('',
                                                                    'int main() {',
                                                                    '    if (1) {',
                                                                    '        printf("hello");',
                                                                    '    return 0;',
                                                                    '        return 1;',
                                                                            '    }',
                                                                            '}'), CursorPath(('a.c', 'main()',
                                                                                      (CursorKind.COMPOUND_STMT, 0),
                                                                                      (CursorKind.IF_STMT, 0),
                                                                                      (CursorKind.COMPOUND_STMT, 0),
                                                                                      (CursorKind.RETURN_STMT, 0))))]]
