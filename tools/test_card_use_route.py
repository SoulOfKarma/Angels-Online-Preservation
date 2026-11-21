"""Comprueba que usar una carta no recorra las cargas pesadas de objetos."""
import ast
import pathlib


ROOT=pathlib.Path(__file__).resolve().parents[1]


def test_card_use_is_ordered_before_generic_item_probes():
    tree=ast.parse((ROOT/'server'/'app.py').read_text(encoding='utf-8'))
    handler=next(
        node for node in ast.walk(tree)
        if isinstance(node,ast.If)
        and isinstance(node.test,ast.BoolOp)
        and isinstance(node.test.values[0],ast.Compare)
        and isinstance(node.test.values[0].left,ast.Name)
        and node.test.values[0].left.id=='opcode'
        and isinstance(node.test.values[0].comparators[0],ast.Constant)
        and node.test.values[0].comparators[0].value==0x002E
    )

    def calls(name):
        return [
            node.lineno for node in ast.walk(handler)
            if isinstance(node,ast.Call)
            and isinstance(node.func,ast.Attribute)
            and node.func.attr==name
        ]

    card_route=min(calls('registrar'))
    assert card_route<min(calls('use_plan'))
