import os
from typing import Iterable, Dict, Any, Type, List

import git

from changes.change import Change, T, Conflict
from repo_state import RepoState
from smart_repo import SmartRepo


class FileAdded(Change):

    def __init__(self, file_name: str, content: List[bytes]):
        self.file_name = file_name
        self.content = content

    @classmethod
    def name(cls) -> str:
        return 'file-added'

    def apply(self, repo: git.Repo, repo_state: RepoState) -> None:
        repo_state[self.file_name] = self.content

    def transform(self, other: 'Change'):
        if isinstance(other, FileAdded):
            if self.file_name != other.file_name:
                return self
            if self.content != other.content:
                raise Conflict
            return None
        if isinstance(other, FileDeleted):
            # Even if we're deleting the file we're gonna add, no modifications are required.
            return self
        raise Conflict

    def to_json(self) -> Dict[str, Any]:
        return dict(super(FileAdded, self).to_json(), **{'file_name': self.file_name,
                                                         'content': [line.decode('ascii') for line in self.content]})

    @classmethod
    def from_json(cls, repo: SmartRepo, json: Dict[str, Any]) -> 'FileAdded':
        return FileAdded(file_name=json['file_name'], content=[line.encode('ascii') for line in json['content']])

    @classmethod
    def detect(cls: Type[T], repo: git.Repo, diff: git.DiffIndex) -> Iterable[T]:
        for add in diff.iter_change_type('A'):
            yield FileAdded(add.b_path, add.b_blob.data_stream.read().splitlines(keepends=True))


class FileDeleted(Change):

    def __init__(self, file_name: str, content: List[str]):
        self.file_name = file_name
        self.content = content

    @classmethod
    def name(cls) -> str:
        return 'file-deleted'

    def apply(self, repo: git.Repo, repo_state: RepoState) -> None:
        del repo_state[self.file_name]

    def transform(self, repo: git.Repo, other: 'Change'):
        if isinstance(other, FileAdded):
            if self.file_name == other.file_name:
                raise Conflict
            return self
        if isinstance(other, FileDeleted):
            if self.file_name == other.file_name:
                # File was already deleted.
                return None
            return self
        if isinstance(other, FileRenamed):
            if self.file_name == other.from_name:
                if open(os.path.join(repo.working_dir, other.to_name)).readlines() == self.content:
                    return FileDeleted()
        raise Conflict

    def to_json(self) -> Dict[str, Any]:
        return dict(super(FileDeleted, self).to_json(), **{'file_name': self.file_name, 'content': self.content})

    @classmethod
    def from_json(cls, repo: SmartRepo, json: Dict[str, Any]) -> 'FileDeleted':
        return FileDeleted(file_name=json['file_name'], content=json['content'])

    @classmethod
    def detect(cls: Type[T], repo: git.Repo, diff: git.DiffIndex) -> Iterable[T]:
        for delete in diff.iter_change_type('D'):
            yield FileDeleted(delete.a_path, delete.a_blob.data_stream.read().splitlines(keepends=True))


class FileRenamed(Change):

    def __init__(self, from_name: str, to_name: str):
        self.from_name = from_name
        self.to_name = to_name

    @classmethod
    def name(cls) -> str:
        return 'file-renamed'

    def apply(self, repo: git.Repo, repo_state: RepoState) -> None:
        repo_state.rename(self.from_name, self.to_name)

    def transform(self, other: 'Change'):
        if isinstance(other, FileAdded):
            if self.to_name == other.file_name:
                # We were about to rename a file to a name and someone else just added a file with that name.
                raise Conflict
            return self
        if isinstance(other, FileDeleted):
            if self.from_name == other.file_name:
                # The file we were about to rename was deleted
                raise Conflict
            return self
        if isinstance(other, FileRenamed):
            if self.from_name == other.from_name:
                # Someone renamed our file to a different name!
                raise Conflict
            if self.to_name == other.to_name:
                # Someone renamed another file to our target name.
                raise Conflict
            return self
        raise Conflict

    def to_json(self) -> Dict[str, Any]:
        return dict(super(FileRenamed, self).to_json(), **{'from_name': self.from_name, 'to_name': self.to_name})

    @classmethod
    def from_json(cls, repo: SmartRepo, json: Dict[str, Any]) -> 'FileRenamed':
        return FileRenamed(from_name=json['from_name'], to_name=json['to_name'])

    @classmethod
    def detect(cls, repo: git.Repo, diff: git.DiffIndex) -> Iterable['FileRenamed']:
        for rename in diff.iter_change_type('R'):
            yield FileRenamed(rename.a_path, rename.b_path)
