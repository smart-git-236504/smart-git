import abc
from typing import Dict, Any, Type, Iterable, TypeVar, Optional

import git

from repo_state import RepoState
from smart_repo import SmartRepo

T = TypeVar('T')


class Change(metaclass=abc.ABCMeta):
    """
    Base class for all repository changes.

    Make sure to add subclasses of this class to changes.CHANGE_CLASSES.
    """

    @classmethod
    @abc.abstractmethod
    def name(cls) -> str:
        pass

    @abc.abstractmethod
    def apply(self, repo: SmartRepo, repo_state: RepoState) -> None:
        """
        Apply this change to the given tree.

        :param repo: The repository to apply the change to.
        :param repo_state: A repo state to apply changes to.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def transform(self: T, repo: SmartRepo, other: 'Change') -> Optional[T]:
        """
        Transform this change given another change that has been applied to the repository.

        For example, the change 'add the line a += 1', when transformed with other='rename a to b', will yield a new
        change 'add the line b += 1'. If other conflicts with self, this will raise a 'Conflict'.
        :param other: The change to transform this one with.
        :param repo: The repository with `other` already applied.
        :return: A new change equivalent to this change applied on a repo that 'other' was previously applied on, or
        None if this change is irrelevant given 'other'.
        """
        raise Conflict

    @abc.abstractmethod
    def to_json(self) -> Dict[str, Any]:
        """
        Serialize this change to JSON.
        """
        return {'type': self.name()}

    @classmethod
    @abc.abstractmethod
    def from_json(cls: Type[T], json: Dict[str, Any]) -> T:
        """
        Restore a change from a previously serialized JSON.
        :param json: A JSON representation of a Change of this type (as returned from `to_json`)
        :return: A Change object of the same type.
        """
        raise NotImplementedError

    def __eq__(self, other):
        if not isinstance(other, Change):
            return False
        return self.to_json() == other.to_json()

    def __repr__(self):
        return f'{self.__class__.__name__}{repr(self.to_json())}'

    @classmethod
    @abc.abstractmethod
    def detect(cls: Type[T], repo: SmartRepo, diff: git.DiffIndex) -> Iterable[T]:
        """
        Given a repository and diff, detects changes of this type that might have occured to cause the given diff.
        :param repo: A git repository.
        :param diff: A collection of diffs in the given repository.
        :return: Changes of this type that might have occurred.
        """
        raise NotImplementedError


class Conflict(RuntimeError):
    pass
