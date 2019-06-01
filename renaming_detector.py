from typing import List, Dict

import clang.cindex

from cursor_path import CursorPath
from utils.ast import search_ast

"""
For mac clanglib.so should be under:
"/Applications/Xcode.app/Contents/Developer/Toolchains/XcodeDefault.xctoolchain/usr/lib/"
"""


class RenamingDetector:
    def __init__(self, index: clang.cindex.Index):
        self.index = index

    def get_renamed_variables(self, file_name: str, first_file: str, second_file: str):
        def is_variable_definition(cursor):
            return cursor.is_definition and cursor.kind == clang.cindex.CursorKind.VAR_DECL
        first_tu = self.index.parse(first_file)
        second_tu = self.index.parse(second_file)
        return self.match_renamed_variables(file_name, first_tu,
                                            list(search_ast(first_tu, file_name, is_variable_definition)), second_tu,
                                            list(search_ast(second_tu, file_name, is_variable_definition)))

    @staticmethod
    def match_renamed_variables(file_name: str, a_tu: clang.cindex.TranslationUnit, a_vars: List[CursorPath],
                                b_tu: clang.cindex.TranslationUnit, b_vars: List[CursorPath]) -> Dict[CursorPath, str]:
        a_mismatches = set(a_vars) - set(b_vars)
        b_mismatches = set(b_vars) - set(a_vars)
        possible_renames = {
            variable: {candidate for candidate in b_mismatches if candidate.path[:-1] == variable.path[:-1]}
            for variable in a_mismatches
        }

        def is_rename(a: CursorPath, b: CursorPath):
            var_a = a.locate(a_tu, file_name)
            var_b = b.locate(b_tu, file_name)
            return var_a.spelling != var_b.spelling and var_a.type.spelling == var_b.type.spelling

        actual_renames = {variable: {candidate for candidate in candidates if is_rename(variable, candidate)}
                          for variable, candidates in possible_renames.items()}

        return {variable: next(iter(candidates)).locate(b_tu, file_name).spelling
                for variable, candidates in actual_renames.items() if len(candidates) == 1}
