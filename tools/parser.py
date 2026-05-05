# This code is freely distributable under the terms of the [MIT license]
# Copyright (c) 2026 Nick N. Zinovenko

import re
import xml.etree.ElementTree as ET

from os.path import commonprefix
from dataclasses import dataclass, field, fields
from pprint import pprint


@dataclass
class PyFunc:
    name: str
    args: list[str] = field(default_factory=list)
    returns: list[str] = field(default_factory=list)


@dataclass
class VsArg:
    name: str
    type: str
    is_var: bool  # VAR prefix: out value (passed by ref)
    struct: list[str] | None  # list of arg suffixes: ptX,ptY,ptZ become pt, struct:[X,Y,Z]
    variadic: int | None  # index of variadic '...' in pascal arg declaration


@dataclass
class VsFunc:
    name: str
    returns: str | None
    args: list[VsArg] = field(default_factory=list)


@dataclass
class Deprecated:
    since: int
    severity: str | None


@dataclass
class XmlArg:
    name: str
    type: str


@dataclass
class XmlFunc:
    name: str
    returns: str | None
    args: list[XmlArg] = field(default_factory=list)
    see_also: list[str] = field(default_factory=list)
    deprecated: Deprecated | None = None

    def __repr__(self):
        node_fields = []
        for field in fields(self):
            value = getattr(self, field.name)
            if value is not None and (not isinstance(value, list) or len(value) > 0):
                node_fields.append(f"{field.name}={value!r}")

        return f"{self.__class__.__name__}({', '.join(node_fields)})"


def parse_pascal_func(source: str) -> VsFunc:
    regex = re.compile(
        r"(?:FUNCTION|PROCEDURE)\s+(?P<func>\w+)(?:\((?P<args>.+)\))?(?:\s*:\s*(?P<ret>.+))?;"
    )
    if match := regex.search(source):
        func = VsFunc(match['func'], match['ret'])
        if args := match['args']:
            for arg in args.split(';'):
                left_part, arg_type = arg.split(':', 1)
                arg_type = arg_type.strip()

                name_part, var_attr = re.subn(r'\bVAR ', '', left_part)
                name_list = [n.strip() for n in name_part.split(',')]

                isStruct = len(name_list) > 1
                isVariadic = '...' in name_list
                variadicIdx = None
                if isStruct and isVariadic:
                    variadicIdx = name_list.index('...')
                    name_list.remove('...')

                arg_name = commonprefix(name_list) if isStruct else name_list[0]
                arg_list = [n.removeprefix(arg_name) for n in name_list] if isStruct else None

                func.args.append(
                    VsArg(
                        name=arg_name,
                        type=arg_type,
                        is_var=bool(var_attr),
                        struct=arg_list,
                        variadic=variadicIdx,
                    )
                )
        return func


def create_pascal_func(func: VsFunc) -> str:
    prefix = "FUNCTION" if func.returns else "PROCEDURE"

    arg_list = []
    for arg in func.args:
        if arg.struct:
            args = [f"{arg.name}{suffix}" for suffix in arg.struct]
            if arg.variadic: args.insert(arg.variadic, '...')  # fmt: skip
            sep = ", " if not arg.variadic else ","
            names = sep.join(args)
        else:
            names = arg.name

        var_attr = "VAR " if arg.is_var else ""
        arg_list.append(f"{var_attr}{names}:{arg.type}")

    args_block = f"({'; '.join(arg_list)})" if arg_list else ""
    ret_block = f" : {func.returns}" if func.returns else ""

    return f"{prefix} {func.name}{args_block}{ret_block};"


def parse_python_func(source: str) -> PyFunc:
    statement = source.split('=', 1)
    func_expr = statement.pop()

    regex = re.compile(r"vs\.(?P<func>\w+)\((?P<args>[^)]*)\)")
    if match := regex.search(func_expr):
        func_name = match['func']
        args_expr = match['args']
        func_args = [n.strip() for n in args_expr.split(',')]

        func_rets = []
        if statement:  # expr on left side of =
            ret_expr = statement.pop().strip('() ')
            func_rets = [n.strip() for n in ret_expr.split(',')]

        return PyFunc(func_name, func_args, func_rets)


def create_python_func(func: PyFunc) -> str:
    args_str = ", ".join(arg for arg in func.args if arg)
    func_expr = f"vs.{func.name}({args_str})"

    if not func.returns:
        return func_expr

    if len(func.returns) > 1:
        ret_expr = f"({', '.join(func.returns)})"
    else:
        ret_expr = func.returns[0]

    return f"{ret_expr} = {func_expr}"


def parse_xml_file(file: str) -> list[XmlFunc]:
    tree = ET.parse(file)
    root = tree.getroot()

    func_list = []
    for item in root.iter('Item'):
        func = XmlFunc(item.findtext('Name'), item.findtext('ReturnType'))

        if (elem := item.find('OldVersion')) is not None:
            func.deprecated = Deprecated(int(elem.text), elem.get('Mode'))

        if (text := item.findtext('SeeAlso')) is not None:
            func.see_also = [n.strip() for n in text.split(',')]

        func_list.append(func)
    return func_list


if __name__ == "__main__":
    import difflib

    with open('data/vs.py') as inFile:
        print(f"🧪 Testing python parser...")
        for line in inFile:
            if match := re.match(r"\t\tPython: (.+)", line):
                org = match[1]
                data = parse_python_func(org)
                gen = create_python_func(data)

                if org != gen:
                    print('❌')
                    print('\n'.join(difflib.ndiff([org], [gen])))

    with open('data/vs.py') as inFile:
        print(f"🧪 Testing pascal parser...")
        for line in inFile:
            if match := re.match(r"\t\tVectorScript: (.+)", line):
                org = match[1]
                data = parse_pascal_func(org)
                gen = create_pascal_func(data)

                if org != gen:
                    print('❌')
                    print('\n'.join(difflib.ndiff([org], [gen])))
