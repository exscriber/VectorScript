# This code is freely distributable under the terms of the [MIT license]
# Copyright (c) 2026 Nick N. Zinovenko


import re
from datetime import datetime
from enum import Enum
from pprint import pformat, pprint
from typing import NamedTuple

import libcst as cst
import libcst.matchers as m
from libcst.display import dump
import parser


class cfg:
    keepComments = True
    keepCommentTypes = False
    keepVectorStript = False
    markDeprecated = True
    reStructuredText = False

    # emit imports into file
    Imports = [
        "from enum import IntFlag",
        "from typing import Any, Callable",
        "from warnings import deprecated",
    ]

    # emit types into file
    TypeDefs = {
        'Point2': 'tuple[float, float]',
        'Point3': 'tuple[float, float, float]',
        'Vector3': 'tuple[float, float, float]',
        'ColorRGB': 'tuple[int, int, int]',
    }

    # VS -> Python types translation table
    Types = {
        'ANY': 'Any',
        'ARRAY': 'list',
        # Pointers
        'HANDLE': 'Handle',
        'PROCEDURE': 'Callable',
        # Numbers
        'BOOLEAN': 'bool',
        'INTEGER': 'int',
        'LONGINT': 'int',
        'REAL': 'float',
        'REAL (Coordinate)': 'float',
        # Strings
        'CHAR': 'str',
        'STRING': 'str',
        'CRITERIA': 'str',
        'DYNARRAY OF CHAR': 'str',
        'DYNARRAY of CHAR': 'str',
        'DYNARRAY[] of CHAR': 'str',
        # Structs
        'POINT': 'Point2',
        'POINT3D': 'Point3',
        'VECTOR': 'Vector3',
        'COLOR': 'ColorRGB',
        'TEXTSTYLE': 'IntFlag',
    }

    # HACK: rename function args
    RenameArgs = {
        'c': 'criteria',
        'orgin': 'origin',
        'ro': 'row',
    }

    # HACK: fix function args
    FixArgTypes = {
        'Poly': 'Point2',
        'Poly3D': 'Point3',
    }

    # HACK: treat functions as variadic (*args)
    # TODO: fill list with parser instead of hardcoding
    VarArgFuncs = [
        'Concat',
        'Message',
        'Poly',
        'Poly3D',
        'Write',
        'WriteBin',
        'WriteLn',
        'WriteLnMac',
        'WriteMac',
    ]


class State(Enum):
    Idle = 0
    inFunc = 1
    inArgs = 2
    inRet = 3


# Decorate class methods with @property getters and setters
class ClassWalker(cst.CSTTransformer):
    @staticmethod
    def create_class_methods(methods_dict: dict[str, str]) -> list[cst.FunctionDef]:
        result = []
        for method, docstring in methods_dict.items():
            match method:  # HACK: hardcoded method typing
                case 'next' | 'prev' | 'first' | 'last':
                    ret_type, is_setter = 'Handle', False
                case 'parent' | 'aux':
                    ret_type, is_setter = 'Handle', True
                case 'locked' | 'selected':
                    ret_type, is_setter = 'bool', True
                case 'name':
                    ret_type, is_setter = 'str', True
                case 'type':
                    ret_type, is_setter = 'int', False

            if result:
                result.append(cst.EmptyLine())

            getter = cst.FunctionDef(
                name=cst.Name(method),
                params=cst.Parameters([cst.Param(cst.Name("self"))]),
                body=(
                    cst.IndentedBlock([
                        cst.SimpleStatementLine([cst.Expr(cst.SimpleString(f'"""{docstring}"""'))])
                    ])
                    if docstring
                    else cst.SimpleStatementSuite([cst.Expr(cst.Ellipsis())])
                ),
                decorators=[cst.Decorator(cst.Name("property"))],
                returns=cst.Annotation(cst.Name(ret_type)),
            )
            result.append(getter)

            setter = cst.FunctionDef(
                name=cst.Name(method),
                params=cst.Parameters([
                    cst.Param(cst.Name("self")),
                    cst.Param(cst.Name("value"), cst.Annotation(cst.Name(ret_type))),
                ]),
                body=cst.SimpleStatementSuite([cst.Expr(cst.Ellipsis())]),
                decorators=[cst.Decorator(cst.Attribute(cst.Name(method), cst.Name("setter")))],
            )
            if is_setter:
                result.append(setter)

        return result

    def visit_ClassDef(self, node):
        default_methods = {
            'Handle': ['type', 'name', 'locked', 'selected', 'parent', 'aux', 'next', 'prev'],
            'HandleContainer': ['first', 'last'],
        }
        method_list = default_methods.get(node.name.value, [])
        self.methods = {x: '' for x in method_list}

    def visit_FunctionDef(self, node):
        self.methods[node.name.value] = node.get_docstring()
        return False

    def leave_ClassDef(self, original_node, updated_node):
        changes: dict[str, cst.CSTNode] = {}
        changes['body'] = cst.IndentedBlock(self.create_class_methods(self.methods))
        if updated_node.name.value == 'HandleContainer':
            changes['bases'] = [cst.Arg(cst.Name('Handle'))]
        return updated_node.with_changes(**changes)


# Extract type hints from comments and assign them as python type annotations
class ParamWalker(cst.CSTTransformer):
    class Param(NamedTuple):
        name: str
        desc: str
        py_type: str
        vs_type: str

    def __init__(self, func_name: str):
        self.func_name = func_name
        self.arg_list: list[ParamWalker.Param] = []

    def visit_Param(self, node):
        self.name = node.name.value
        self.desc = None
        self.py_type = None
        self.vs_type = None

    def visit_Comment(self, node):
        if match := re.match(r"# (?:in/out )?(?P<type>.+?)\s*- (?P<desc>.*)", node.value):
            self.desc = match['desc'].strip()
            self.vs_type = match['type']

    def leave_Comment(self, original_node, updated_node):
        if cfg.keepComments:
            return (
                updated_node
                if cfg.keepCommentTypes
                else updated_node.with_changes(value=f'# {self.desc}')
            )
        return cst.RemoveFromParent()

    def leave_TrailingWhitespace(self, original_node, updated_node):
        ws = '  ' if updated_node.comment else ''
        return updated_node.with_changes(whitespace=cst.SimpleWhitespace(ws))

    def leave_Param(self, original_node, updated_node):
        changes: dict[str, cst.CSTNode] = {}

        # trailing comma changes: remove spaces before comma and make it mandatory
        if isinstance(updated_node.comma, cst.Comma):
            new_comma = updated_node.comma.with_changes(whitespace_before=cst.SimpleWhitespace(''))
            changes['comma'] = new_comma
        else:
            changes['comma'] = cst.Comma(whitespace_after=updated_node.whitespace_after_param)
            changes['whitespace_after_param'] = cst.SimpleWhitespace('')

        # rename parameters
        if new_name := cfg.RenameArgs.get(updated_node.name.value):
            self.name = new_name
            changes['name'] = cst.Name(new_name)

        # assign type hints
        if hint := cfg.Types.get(self.vs_type, 'argTypeError'):
            self.py_type = hint
            changes['annotation'] = cst.Annotation(cst.parse_expression(hint))

        # HACK: Poly, Poly3D arg types wrong - fix them here
        if fix_hint := cfg.FixArgTypes.get(self.func_name):
            self.py_type = fix_hint
            changes['annotation'] = cst.Annotation(cst.Name(fix_hint))

        self.arg_list.append(self.Param(self.name, self.desc, self.py_type, self.vs_type))
        return updated_node.with_changes(**changes)

    def leave_Parameters(self, original_node, updated_node):
        if not updated_node.params:
            return updated_node

        changes: dict[str, cst.CSTNode] = {}

        # Align trailing comments
        if cfg.keepComments:
            arg_length = [len(f"{arg.name}: {arg.py_type},") for arg in self.arg_list]
            max_length = max(arg_length) + 2
            new_params = []
            for param, length in zip(updated_node.params, arg_length):
                ws = ' ' * (max_length - length)
                ws_node = param.comma.whitespace_after.first_line.whitespace
                new_params.append(param.with_deep_changes(ws_node, value=ws))
            changes['params'] = new_params

        # HACK: Variadic functions: change arg into *arg...
        if self.func_name in cfg.VarArgFuncs:
            changes['params'] = []
            changes['star_arg'] = updated_node.params[0].with_changes(star='*')

        return updated_node.with_changes(**changes)


class ModuleWalker(cst.CSTTransformer):
    def __init__(self, data: dict[str, parser.XmlFunc] = {}):
        self.xml_data = data
        self.state = State.Idle

    def visit_Module(self, node):
        self.default_indent = node.default_indent

    # Skip over: we will take care of class methods in ClassWalker
    def visit_ClassDef(self, node):
        return False

    def leave_ClassDef(self, original_node, updated_node):
        return updated_node.visit(ClassWalker())

    def visit_FunctionDef(self, node):
        self.state = State.inFunc
        self.func_name = node.name.value
        self.arg_list: list[ParamWalker.Param] = []
        self.ret_desc: list[str] = []

    # Skip over: we will take care of params in ParamWalker
    def visit_Parameters(self, node):
        return False

    def leave_Parameters(self, original_node, updated_node):
        new_node = updated_node.visit(walker := ParamWalker(self.func_name))
        self.arg_list = walker.arg_list
        return new_node

    def visit_Return(self, node):
        self.state = State.inRet

    # Gather comments inside and after return statement
    def visit_Comment(self, node):
        if self.state is State.inRet:
            for line in node.value[2:].split('[[BR]]'):
                if line:
                    self.ret_desc.append(line)

    def leave_Return(self, original_node, updated_node):
        return cst.RemoveFromParent()

    # TODO: refactor this code into smaller parts...
    def leave_FunctionDef(self, original_node, updated_node):
        self.state = State.Idle
        changes: dict[str, cst.CSTNode] = {}

        # XML data infusion
        see_also = None
        if func_xml := self.xml_data.get(updated_node.name.value):
            # @deprecated decorator
            if func_xml.deprecated and cfg.markDeprecated:
                v = func_xml.deprecated.since / 100
                version = v + 1995 if v > 13 else v
                message = f"Deprecated since VW {version}"
                if severity := func_xml.deprecated.severity:
                    message += f" {severity}"
                decorator = cst.Decorator(
                    cst.Call(
                        func=cst.Name("deprecated"),
                        args=[cst.Arg(cst.SimpleString(f'"{message}"'))],
                    )
                )
                changes['decorators'] = [decorator]

            # See also markdown formatting
            if func_xml.see_also:
                items = [f":func:`{item}`" for item in func_xml.see_also]
                see_also = f"See also: {', '.join(items)}"

        # docstring transformation
        if docstring := updated_node.get_docstring():
            code_py, code_vs, _, category, *desc = docstring.splitlines()
            func_py = parser.parse_python_func(code_py.removeprefix('Python: '))
            func_vs = parser.parse_pascal_func(code_vs.removeprefix('VectorScript: '))

            # python return consist of pascal: RETURN, VAR arg1, VAR arg2,...
            ret_names: list[str] = []
            ret_types: list[str] = []
            for arg in func_vs.args:
                if not arg.is_var:
                    continue
                ret_names.append(arg.name)
                ret_type = cfg.Types.get(arg.type, 'retTypeError')

                if arg.struct and not arg.variadic:
                    match len(arg.struct):
                        case 2:  # there is only one struct of 2 values
                            ret_types.append('Point2')
                        case 3:  # guess by name: p, pt, point,...
                            arg_type = 'Point3' if 'p' in arg.name.lower() else 'Vector3'
                            ret_types.append(arg_type)
                        case _:
                            ret_types.append('retTypeError')
                elif arg.variadic:
                    ret_types.append(f"tuple[{ret_type},...]")
                else:
                    ret_types.append(ret_type)

            if func_vs.returns:
                ret_names.insert(0, func_vs.returns)
                ret_types.insert(0, cfg.Types.get(func_vs.returns.upper(), 'retTypeError'))

            # HACK: if Python and Vectorscript docstring code differ:
            # it most likely due to Python have extra phantom return
            # so we derive correct Python docstring from VectorScript and move on...
            if len(ret_names) != len(func_py.returns):
                func_py.returns = ret_names
                code_py = f"Python: {parser.create_python_func(func_py)}"

            ret_stmt = (
                f"tuple[{', '.join(ret_types)}]"
                if len(ret_types) > 1
                else (ret_types[0] if ret_types else 'None')
            )
            changes['returns'] = cst.Annotation(cst.parse_expression(ret_stmt))

            doc_blocks = [desc, self.ret_desc]

            code_block = [code_py]
            if cfg.keepVectorStript:
                code_block.append(code_vs)
            doc_blocks.append(code_block)

            if cfg.reStructuredText:
                rst_args = [f":param {arg.name}: {arg.desc}" for arg in self.arg_list]
                rst_rets = [f":return {n}: {t}" for n, t in zip(ret_names, ret_types)]
                doc_blocks.append(rst_args + rst_rets)

            if see_also:
                doc_blocks.append([see_also])

            doc_blocks.append([category])

            indent = self.default_indent
            doc_lines = "\n\n".join("  \n".join(b) for b in doc_blocks if b).splitlines()
            docstring = "\n".join((f"{indent}{line}" if line else '') for line in doc_lines)
            raw = "r" if "\\" in docstring else ""  # use r""" when docstring contains \

            docstring_stmt = cst.SimpleStatementLine(
                body=[cst.Expr(cst.SimpleString(f'{raw}"""\n{docstring}\n{indent}"""'))]
            )
            pass_stmt = cst.SimpleStatementLine([cst.Pass()])
            changes['body'] = cst.IndentedBlock(body=[docstring_stmt, pass_stmt])

        return updated_node.with_changes(**changes)

    def leave_Module(self, original_node, updated_node):
        version_tag = datetime.now().strftime(r"%Y.%m.%d")
        return updated_node.with_changes(
            body=[
                cst.parse_statement(f'__version__ = "{version_tag}"'),
                cst.EmptyLine(),
                *(cst.parse_statement(v) for v in cfg.Imports),
                cst.EmptyLine(),
                *(cst.parse_statement(f"type {k} = {v}") for k, v in cfg.TypeDefs.items()),
                cst.EmptyLine(),
                *updated_node.body,
            ]
        )


if __name__ == "__main__":
    import os

    os.makedirs('build/ast', exist_ok=True)

    xml_func_list = parser.parse_xml_file('data/VectorScript Reference.xml')
    xml_data = {func.name: func for func in xml_func_list}

    with open('data/vs.py') as file:
        content = file.read()

    source = cst.parse_module(content)
    result = source.visit(walker := ModuleWalker(xml_data))

    with open('build/result.py', 'w') as outFile:
        outFile.write(result.code)

    # with open('build/ast/source.ast', 'w') as outFile:
    #     outFile.write(repr(source))

    # with open('build/ast/result.ast', 'w') as outFile:
    #     outFile.write(dump(result))
