import abc
from io import BytesIO
from typing import Tuple, List, Callable, Optional

import git
from gitdb import IStream

from smart_repo import SmartRepo
from utils.file import file_from_text


class RepoState(metaclass=abc.ABCMeta):

    def __init__(self, repo: SmartRepo):
        self.repo = repo

    @abc.abstractmethod
    def __setitem__(self, file_name: str, contents: List[bytes]):
        """ Create/change the contents of a file. """
        raise NotImplementedError

    @abc.abstractmethod
    def __getitem__(self, file_name: str) -> List[bytes]:
        """ Return the contents of the given file as a list of lines (with line endings). """
        raise NotImplementedError

    def ast(self, file_name: str):
        """ Return the parsed AST of the given file """
        with file_from_text(self[file_name], path=file_name) as file:
            return self.repo.get_cindex().parse(file.name)

    @abc.abstractmethod
    def rename(self, from_name: str, to_name: str) -> None:
        raise NotImplementedError

    def __delitem__(self, file_name: str):
        """ Delete a file. """
        raise NotImplementedError


class SingleFileRepoState(RepoState):

    def __init__(self, repo: SmartRepo, path: str, content: Optional[List[bytes]]=None):
        super(SingleFileRepoState, self).__init__(repo)
        self.path = path
        self.content = content

    def __setitem__(self, file_name: str, contents: List[bytes]):
        if file_name != self.path:
            raise KeyError(f'Only writes to {self.path} are supported.')
        self.content = contents

    def __getitem__(self, file_name: str) -> List[bytes]:
        if file_name != self.path:
            raise KeyError(f'Only reads from {self.path} are supported.')
        return self.content

    def rename(self, from_name: str, to_name: str) -> None:
        raise NotImplementedError(f'Renaming not supported in {self.__class__.__name__}')

    def __delitem__(self, file_name: str):
        if file_name != self.path:
            raise KeyError(f'Only deletes of {self.path} are supported.')
        self.content = None


class TreeBackedRepoState(RepoState):
    """
    Abstracts a state of a repository into a simple object that allows retrieving, modifying and deleting files by
    filename.
    """

    def __init__(self, repo: SmartRepo, tree: git.Tree):
        super(TreeBackedRepoState, self).__init__(repo)
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
        return self.tree[file_name].data_stream.read().splitlines(keepends=True)

    def rename(self, from_name: str, to_name: str) -> None:
        """ Rename a file. """
        binsha = self.tree[from_name].binsha
        del self[from_name]
        tree, name = self._get_subtree(to_name)
        self.tree = self._modify(self.tree, lambda t: t.add(binsha, git.Blob.file_mode, name))

    def __delitem__(self, file_name: str):
        tree, name = self._get_subtree(file_name)
        self.tree = self._modify(self.tree, lambda t: t.__delitem__(name))


