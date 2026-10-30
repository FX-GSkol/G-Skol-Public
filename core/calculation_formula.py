"""Normalisation et validation des formules arithmétiques G-Skol.

Les références aux champs sont conservées sous la forme {identifiant}.
"""
import ast
import re

_NUM = re.compile(r"(?<![\w.])\d+(?:[.,]\d+)?(?![\w.])")
_REF = re.compile(r"\{[^{}]+\}")


def normalize(expression):
    """Accepte les crochets de regroupement et la virgule décimale."""
    expression = str(expression or "")
    expression = expression.replace("[", "(").replace("]", ")")
    return _NUM.sub(lambda match: match.group().replace(",", "."), expression)


def validate(expression):
    """Valide une formule sans l'exécuter et sans accepter de code Python."""
    expression = normalize(expression)
    expression = _REF.sub("1", expression)
    tree = ast.parse(expression, mode="eval")
    def check(node):
        if isinstance(node, ast.Expression):
            return check(node.body)
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            return
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            return check(node.operand)
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
            check(node.left)
            check(node.right)
            return
        raise ValueError("Utilisez uniquement des nombres, des champs, +, -, *, /, ( ) et [ ].")
    check(tree)
    return expression
