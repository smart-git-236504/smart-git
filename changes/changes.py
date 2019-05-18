from typing import Any, Dict

from changes.change import Change


def change_from_json(change: Dict[str, Any]) -> Change:
    """
    Given a change JSON, decodes it as a Change object of a certain type.
    :param change:
    :return:
    """
    from changes import CHANGE_CLASSES
    return next(change_class for change_class in CHANGE_CLASSES if change_class.name() == change['type'])\
        .from_json(change)
