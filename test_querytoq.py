#!/usr/bin/env python
"""Test QueryToQ transformer with specific examples"""

from lark import Lark, Transformer
from django.db.models import Q

# Lark grammar for parsing natural language queries about table names
table_query_grammar = r"""
    ?start: expression

    ?expression: or_expr
    
    ?or_expr: and_expr ("OR" and_expr)*
    ?and_expr: atom ("AND" atom)*
    
    ?atom: comparison
         | "(" expression ")"
         | "NOT" atom
    
    comparison: "name" operator value
    
    operator: "=" | "!=" | "CONTAINS" | "STARTS_WITH" | "ENDS_WITH"
    
    value: ESCAPED_STRING
    
    %import common.ESCAPED_STRING
    %import common.WS
    %ignore WS
"""

class QueryToQ(Transformer):
    """Transform Lark parse tree to Django Q objects"""

    def start(self, args):
        print(f"start: args={args}")
        return args[0]

    def or_expr(self, args):
        print(f"or_expr: args={args}")
        if len(args) == 1:
            return args[0]
        q = args[0]
        for arg in args[1:]:
            q |= arg
        return q

    def and_expr(self, args):
        print(f"and_expr: args={args}")
        if len(args) == 1:
            return args[0]
        q = args[0]
        for arg in args[1:]:
            q &= arg
        return q

    def atom(self, args):
        print(f"atom: args={args}")
        if len(args) == 2 and args[0] == "NOT":
            return ~args[1]
        return args[0]

    def comparison(self, args):
        print(f"comparison: args={args}")
        field, op, value = args
        return self._build_q(str(op), str(value))

    def operator(self, args):
        print(f"operator: args={args}")
        return str(args[0])

    def value(self, args):
        print(f"value: args={args}")
        # Remove quotes from string
        return str(args[0])[1:-1]

    def _build_q(self, op: str, value: str) -> Q:
        """Build Django Q object for name field"""
        print(f"_build_q: op={op}, value={value}")
        if op == "=":
            return Q(name__exact=value)
        elif op == "!=":
            return ~Q(name__exact=value)
        elif op == "CONTAINS":
            return Q(name__icontains=value)
        elif op == "STARTS_WITH":
            return Q(name__istartswith=value)
        elif op == "ENDS_WITH":
            return Q(name__iendswith=value)
        return Q()


# Test the specific examples
parser = Lark(table_query_grammar, parser="lalr")
transformer = QueryToQ()

test_cases = [
    'name STARTS_WITH "project"',
    'name = "project"',
    'name CONTAINS "test"',
    'name != "backup"',
]

for test in test_cases:
    print(f"\n{'='*50}")
    print(f"Testing: {test}")
    print(f"{'='*50}")
    
    try:
        # Parse
        tree = parser.parse(test)
        print(f"\nParse tree:")
        print(tree.pretty())
        
        # Transform
        q_object = transformer.transform(tree)
        print(f"\nResulting Q object: {q_object}")
        
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()