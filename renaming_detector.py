import clang.cindex

"""
For mac clanglib.so should be under:
"/Applications/Xcode.app/Contents/Developer/Toolchains/XcodeDefault.xctoolchain/usr/lib/"
"""


class RenamingDetector:
    def __init__(self, clang_file_path):
        clang.cindex.Config.set_library_path(clang_file_path)
        self.index = clang.cindex.Index.create()


    def get_renamed_variables(self, first_file, second_file):
        first_file_translation_unit = self.index.parse(first_file)
        self.first_file_vars = []
        self.find_variable_declarations(first_file_translation_unit.cursor, self.first_file_vars)
        second_file_translation_unit = self.index.parse(second_file)
        self.second_file_vars = []
        self.find_variable_declarations(second_file_translation_unit.cursor, self.second_file_vars)
        return self.match_renamed_variables()


    def match_renamed_variables(self):
        """
            Very naive algorithm to detect variable renames between two files.
        """
        renamed_vars = {}
        for var in self.first_file_vars:
            if var in self.second_file_vars:
                self.first_file_vars.remove(var)
                self.second_file_vars.remove(var)
        for var_first_file, var_second_file in zip(self.first_file_vars, self.second_file_vars):
            renamed_vars[var_first_file] = var_second_file
        return renamed_vars



    def find_variable_declarations(self, node, vars_list):
        """
            Find all variables declarations in given file cursor (node)
        """
        if node.is_definition:
            if node.kind == clang.cindex.CursorKind.VAR_DECL:
                print(node.spelling)
                vars_list.append(node.spelling)
        # Recurse for children of this node
        for c in node.get_children():
            self.find_variable_declarations(c, vars_list)

