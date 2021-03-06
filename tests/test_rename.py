from clang.cindex import CursorKind

from changes.file_operations import FileAdded
from changes.variable_rename import VariableRenamed
from repo_state import TreeBackedRepoState
from smart_repo import SmartRepo
from tests.conftest import commit
from utils.file import as_lines
from utils.repo import get_changes


@commit({'a.c': '''int main() {
    int a = 0;
    return a + (a - 1);
}
'''})
def test_apply(smart_repo: SmartRepo):
    state = TreeBackedRepoState(smart_repo, smart_repo.head.commit.tree)
    change = VariableRenamed(smart_repo.find_cursor('a.c', lambda cur: cur.kind == CursorKind.VAR_DECL
                                                                       and cur.spelling == 'a'), 'meow')
    change.apply(smart_repo, state)
    assert state['a.c'] == as_lines('int main() {',
                                    '    int meow = 0;',
                                    '    return meow + (meow - 1);',
                                    '}')


@commit({'a.c': '''
int main() {
    int a = 0;
}
'''}, tag='initial')
@commit({'a.c': '''
int main() {
    int b = 0;
}
'''})
def test_detect(smart_repo: SmartRepo):
    a = smart_repo.find_cursor('a.c', lambda c: c.spelling == 'b').drop(1).appended('a')
    assert get_changes(smart_repo) == [[FileAdded('a.c', smart_repo.contents('a.c', 'initial'))],
                                       [VariableRenamed(a, 'b')]]

