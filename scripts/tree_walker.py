import vs
import sys
from typing import Callable, TypeVar, Optional
from pprint import pformat


def vs_iter(container: vs.HandleContainer):
    child = container.first
    while child:
        yield child
        child = child.next


T_Node = vs.Handle
T_Context = TypeVar('T_Context')


def visit(
    node: T_Node, visitor: Callable[[T_Node, T_Context], Optional[bool]], context: T_Context
) -> T_Context:
    # Call closure and skip over subtree if return is False
    if visitor(node, context) is False:
        return context

    # Symbol instance
    if node.type == 15:
        if sym_def := vs.GetObject(vs.GetSymName(node)):
            node = sym_def

    # Container types: Group, SymDef, Layer, PIO
    if node.type in (11, 16, 31, 86):
        for child in vs_iter(node):
            visit(child, visitor, context)

    return context


#  user provided closure
def on_visit(obj: vs.Handle, ctx: list):
    info = {'type': obj.type, 'parent': obj.parent.type}
    if obj.name not in ('', 'none'):
        info['name'] = obj.name
    if (obj_class := vs.GetClass(obj)) not in ('0', 'None'):
        info['class'] = obj_class
    if obj.type == 15:
        info['symbol'] = vs.GetSymName(obj)
    ctx.append(info)


def callback(obj: vs.Handle):
    if obj.type == 86:  # Plug-In Object
        result = visit(obj, on_visit, list())
        vs.Message(pformat(result, sort_dicts=False))


def run():
    vs.Message(f"{sys.version}\n")
    vs.ForEachObject(callback, "VSEL")


if __name__ == "__main__":
    run()
