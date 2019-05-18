import git

from changes.file_operations import FileAdded
from changes.textual_change import TextualChange
from tests.conftest import commit
from util import get_changes, as_lines


@commit({'a.c': '''
/// asjdlkdsjalkdsa
/// asdkjasdlkjd
/// aaa
'''})
@commit({'a.c': '''
// asjdlkdsjalkdsa
// asdkjasdlkjd
// aaa
'''})
def test_textual(smart_repo: git.Repo):
    assert get_changes(smart_repo) \
        == [[FileAdded('a.c', as_lines('', '/// asjdlkdsjalkdsa', '/// asdkjasdlkjd', '/// aaa'))],
            [TextualChange('a.c', 1, 4, as_lines('// asjdlkdsjalkdsa', '// asdkjasdlkjd', '// aaa'))]]
