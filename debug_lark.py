from lark import Lark

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

parser = Lark(table_query_grammar, parser="lalr", debug=True)

query = 'name STARTS_WITH "project"'
print(f"Parsing: {query}")
tree = parser.parse(query)
print("\nParse tree:")
print(tree.pretty())

print("\nTree structure:")
for i, child in enumerate(tree.children):
    print(f"Child {i}: {child}")
    if hasattr(child, 'children'):
        for j, subchild in enumerate(child.children):
            print(f"  Subchild {j}: {subchild}")
            if hasattr(subchild, 'value'):
                print(f"    Value: {subchild.value}")
            if hasattr(subchild, 'type'):
                print(f"    Type: {subchild.type}")