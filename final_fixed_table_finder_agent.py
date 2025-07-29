# Final fixed version with corrected grammar and transformer

import dspy
from lark import Lark, Transformer, Token
from django.db.models import Q
from typing import Dict, Any, List


# Fixed Lark grammar - operator tokens need to be captured
table_query_grammar = r"""
    ?start: expression

    ?expression: or_expr
    
    ?or_expr: and_expr ("OR" and_expr)*
    ?and_expr: atom ("AND" atom)*
    
    ?atom: comparison
         | "(" expression ")"
         | "NOT" atom
    
    comparison: "name" operator value
    
    operator: EQ | NEQ | CONTAINS | STARTS_WITH | ENDS_WITH
    
    EQ: "="
    NEQ: "!="
    CONTAINS: "CONTAINS"
    STARTS_WITH: "STARTS_WITH" 
    ENDS_WITH: "ENDS_WITH"
    
    value: ESCAPED_STRING
    
    %import common.ESCAPED_STRING
    %import common.WS
    %ignore WS
"""


class QueryTranslator(dspy.Signature):
    """Translate natural language to structured query"""

    natural_query = dspy.InputField(desc="Natural language query about table names")
    structured_query = dspy.OutputField(
        desc="Structured query using: name OPERATOR 'value' with AND/OR/NOT"
    )


class NLToStructuredQuery(dspy.Module):
    """Convert natural language to structured query format"""

    def __init__(self):
        super().__init__()
        self.translator = dspy.ChainOfThought(QueryTranslator)

    def forward(self, query: str) -> str:
        prompt = f"""
        Translate to structured format using these operators:
        - = (exact match)
        - != (not equal)
        - CONTAINS (substring match)
        - STARTS_WITH (prefix match)
        - ENDS_WITH (suffix match)
        
        Examples:
        "table named project" → name = "project"
        "tables with project in name" → name CONTAINS "project"
        "tables starting with user" → name STARTS_WITH "user"
        "not test tables" → NOT name CONTAINS "test"
        "project or task tables" → name CONTAINS "project" OR name CONTAINS "task"
        
        Query: {query}
        """

        result = self.translator(natural_query=prompt)
        return result.structured_query.strip()


class QueryToQ(Transformer):
    """Transform Lark parse tree to Django Q objects"""

    def start(self, items):
        return items[0]

    def or_expr(self, items):
        if len(items) == 1:
            return items[0]
        q = items[0]
        for item in items[1:]:
            if isinstance(item, Q):
                q |= item
        return q

    def and_expr(self, items):
        if len(items) == 1:
            return items[0]
        q = items[0]
        for item in items[1:]:
            if isinstance(item, Q):
                q &= item
        return q

    def atom(self, items):
        if len(items) == 2 and isinstance(items[0], Token) and items[0].value.upper() == "NOT":
            return ~items[1]
        elif len(items) == 1:
            return items[0]
        return items[0]

    def comparison(self, items):
        # The transformer already processed operator and value nodes
        # So items = [operator_result, value_result]
        print(f"comparison items: {items}")
        if len(items) >= 2:
            operator = items[0]  # This is the operator result (string)
            value = items[1]     # This is the value result (string)
            print(f"  operator: {operator}, value: {value}")
            return self._build_q(operator, value)
        return Q()

    def operator(self, items):
        # items should contain the operator token
        if items and isinstance(items[0], Token):
            return items[0].type  # Return the token type (EQ, NEQ, etc.)
        return ""

    def value(self, items):
        # Get the string value and remove quotes
        if items and isinstance(items[0], Token):
            val = items[0].value
            # Strip quotes
            if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                return val[1:-1]
            return val
        return ""

    def _build_q(self, op: str, value: str) -> Q:
        """Build Django Q object for name field"""
        if op == "EQ":
            return Q(name__exact=value)
        elif op == "NEQ":
            return ~Q(name__exact=value)
        elif op == "CONTAINS":
            return Q(name__icontains=value)
        elif op == "STARTS_WITH":
            return Q(name__istartswith=value)
        elif op == "ENDS_WITH":
            return Q(name__iendswith=value)
        return Q()


# ========================================
# Complete Query Pipeline
# ========================================


class DspyLarkQueryBuilder:
    """Pipeline from natural language to Django Q object"""

    def __init__(self):
        # Initialize dspy module
        self.nl_translator = NLToStructuredQuery()

        # Initialize Lark parser
        self.parser = Lark(table_query_grammar, parser="lalr")
        self.transformer = QueryToQ()

    def build_q_object(self, natural_query: str) -> Dict[str, Any]:
        """Convert natural language to Django Q object"""

        # Step 1: Translate to structured query
        structured_query = self.nl_translator.forward(natural_query)

        # Clean up common formatting issues
        structured_query = self._clean_query(structured_query)

        try:
            # Step 2: Parse with Lark
            tree = self.parser.parse(structured_query)

            # Step 3: Transform to Q object
            q_object = self.transformer.transform(tree)

            return {
                "success": True,
                "natural_query": natural_query,
                "structured_query": structured_query,
                "q_object": q_object,
                "tree": tree.pretty(),
            }

        except Exception as e:
            return {
                "success": False,
                "natural_query": natural_query,
                "structured_query": structured_query,
                "error": str(e),
            }

    def _clean_query(self, query: str) -> str:
        """Basic cleaning of dspy output"""
        # Take only the first line (remove explanations)
        query = query.split("\n")[0].strip()

        # Standardize operators
        query = query.replace(" contains ", " CONTAINS ")
        query = query.replace(" starts with ", " STARTS_WITH ")
        query = query.replace(" ends with ", " ENDS_WITH ")
        query = query.replace(" and ", " AND ")
        query = query.replace(" or ", " OR ")
        query = query.replace(" not ", " NOT ")

        return query


if __name__ == "__main__":
    # Test the fixed implementation
    test_queries = [
        'name STARTS_WITH "project"',
        'name = "project"',
        'name CONTAINS "test"',
        'name != "backup"',
        'name ENDS_WITH "_old"',
        'name CONTAINS "project" OR name CONTAINS "task"',
        'NOT name CONTAINS "test"',
    ]

    parser = Lark(table_query_grammar, parser="lalr")
    transformer = QueryToQ()

    for query in test_queries:
        print(f"\nTesting: {query}")
        try:
            tree = parser.parse(query)
            print(f"Parse tree OK")
            
            q_object = transformer.transform(tree)
            print(f"Q object: {q_object}")
            
        except Exception as e:
            print(f"ERROR: {e}")
            import traceback
            traceback.print_exc()