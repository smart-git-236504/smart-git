import os
from collections.__init__ import namedtuple
from contextlib import contextmanager
from tempfile import NamedTemporaryFile
from typing import List, Sequence, Iterable


def as_lines(*lines: str) -> List[bytes]:
    return [f'{line}\n'.encode('utf-8') for line in lines]


Replacement = namedtuple('Replacement', ['line', 'from_column', 'to_column', 'text'])


def apply_replacements(file_text: Sequence[bytes], replacements: Iterable[Replacement]) -> List[bytes]:
    replaced_text = list(file_text)
    replacements_by_line = {}
    for replacement in replacements:
        replacements_by_line.setdefault(replacement.line, []).append(replacement)
    for line, line_replacements in replacements_by_line.items():
        sorted_replacements = sorted(line_replacements, key=lambda replacement: replacement.from_column)
        delta = 0
        for replacement in sorted_replacements:
            prev_line = replaced_text[line]
            replaced_text[line] = prev_line[:replacement.from_column + delta] \
                                  + replacement.text.encode('utf-8') \
                                  + prev_line[replacement.to_column + delta:]
            delta += len(replacement.text) - (replacement.to_column - replacement.from_column)
    return replaced_text


@contextmanager
def file_from_blob(blob):
    with NamedTemporaryFile(suffix=os.path.splitext(blob.path)[-1]) as file:
        file.write(blob.data_stream.read())
        file.flush()
        yield file


@contextmanager
def file_from_text(text: List[bytes], path=''):
    with NamedTemporaryFile(suffix=os.path.splitext(path)[-1]) as file:
        file.write(b''.join(text))
        file.flush()
        yield file