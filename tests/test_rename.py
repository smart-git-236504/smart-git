from git import Repo

from tests.conftest import commit
from tests.util import get_changes


@commit({'a.c': '''
int main() {
    int a = 0;
}
'''})
@commit({'a.c': '''
int main() {
    int b = 0;
}
'''})
def test_basic(smart_repo: Repo):
    assert get_changes(smart_repo) == [[{'action': 'rename', 'from': 'a', 'to': 'b'}]]
