from io import BytesIO
from typing import Tuple, List, Callable

import git
from gitdb import IStream

from smart_repo import SmartRepo


class RepoState(object):
    """
    Abstracts a state of a repository into a simple object that allows retrieving, modifying and deleting files by
    filename.
    """

    def __init__(self, repo: SmartRepo, tree: git.Tree):
        self.repo = repo
        self.tree = tree

    def _get_subtree(self, file_name) -> Tuple[git.Tree, str]:
        tokens = file_name.split('/')
        tree = self.tree
        for token in tokens[:-1]:
            if token not in tree:
                item = git.Tree.new_from_sha(tree.repo, tree.repo.odb.store(IStream(git.Tree.type, 0, BytesIO())))
                item.path = f'{tree.path}/{token}' if tree.path else token
                tree = self._modify(tree, lambda t: t.add(item.binsha, tree.mode, token))
            assert isinstance(token[tree], git.Tree)
            tree = token[tree]
        return tree, tokens[-1]

    def __setitem__(self, file_name: str, contents: List[bytes]):
        """ Create/change the contents of a file. """

        tree, name = self._get_subtree(file_name)
        content = b''.join(contents)
        self.tree = self._modify(self.tree, lambda t: t.add(self.tree.repo.odb.store(IStream(git.Blob.type,
                                                                                             len(content),
                                                                                             BytesIO(content))).binsha,
                                                            git.Blob.file_mode, name, force=True))

    @staticmethod
    def _modify(tree: git.Tree, modifier: Callable[[git.TreeModifier], None]):
        """ Change the given tree and write the modified tree to the object database. """

        temp_tree = git.Tree.new_from_sha(tree.repo, tree.binsha)
        cache = temp_tree.cache
        modifier(cache)
        cache.set_done()
        stream = BytesIO()
        temp_tree._serialize(stream)
        stream.seek(0)
        new_tree = git.Tree.new_from_sha(tree.repo, tree.repo.odb.store(IStream(git.Tree.type, len(stream.getvalue()),
                                                                        stream)).binsha)
        new_tree.path = tree.path
        return new_tree

    def __getitem__(self, file_name: str) -> List[bytes]:
        """ Return the contents of the given file as a list of lines (with line endings). """
        return self.tree[file_name].data_stream.read().splitlines(keepends=True)

    def ast(self, file_name: str):
        """ Return the parsed AST of the given file """
        with self.repo.file_from_text(self[file_name], path=file_name) as file:
            return self.repo.get_cindex().parse(file.name)

    def rename(self, from_name: str, to_name: str) -> None:
        """ Rename a file. """
        binsha = self.tree[from_name].binsha
        del self[from_name]
        tree, name = self._get_subtree(to_name)
        self.tree = self._modify(self.tree, lambda t: t.add(binsha, git.Blob.file_mode, name))

    def __delitem__(self, file_name: str):
        """ Delete a file. """
        tree, name = self._get_subtree(file_name)
        self.tree = self._modify(self.tree, lambda t: t.__delitem__(name))


