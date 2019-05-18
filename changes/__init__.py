from changes.file_operations import FileAdded, FileDeleted, FileRenamed
from changes.textual_change import TextualChange
from changes.variable_rename import VariableRenamed


# Ordered by precedence.
CHANGE_CLASSES = [FileAdded, FileDeleted, FileRenamed, VariableRenamed, TextualChange]
