# Generated from BaserowFormula.g4 by ANTLR 4.9
# encoding: utf-8
from antlr4 import *
from io import StringIO
import sys
if sys.version_info[1] > 5:
	from typing import TextIO
else:
	from typing.io import TextIO


def serializedATN():
    with StringIO() as buf:
        buf.write("\3\u608b\ua72a\u8133\ub9ed\u417c\u3be7\u7786\u5964\3U")
        buf.write("c\4\2\t\2\4\3\t\3\4\4\t\4\4\5\t\5\4\6\t\6\4\7\t\7\3\2")
        buf.write("\3\2\3\2\3\3\3\3\3\3\3\3\3\3\3\3\3\3\3\3\3\3\3\3\3\3\3")
        buf.write("\3\3\3\3\3\3\3\3\3\3\3\3\3\3\3\3\3\3\3\3\3\3\3\3\3\3\3")
        buf.write("\3\3\3\3\5\3-\n\3\3\3\3\3\3\3\3\3\3\3\3\3\3\3\3\3\7\3")
        buf.write("\67\n\3\f\3\16\3:\13\3\5\3<\n\3\3\3\3\3\5\3@\n\3\3\3\3")
        buf.write("\3\3\3\3\3\3\3\3\3\3\3\3\3\3\3\3\3\3\3\3\3\3\3\3\3\3\3")
        buf.write("\3\3\3\3\3\3\3\3\3\3\7\3V\n\3\f\3\16\3Y\13\3\3\4\3\4\3")
        buf.write("\5\3\5\3\6\3\6\3\7\3\7\3\7\2\3\4\b\2\4\6\b\n\f\2\n\3\2")
        buf.write("\6\7\4\2\20\20KK\4\2??EE\4\2+,\66\67\4\2\'\'))\3\2\3\5")
        buf.write("\3\2\33\34\3\2\35\36\2p\2\16\3\2\2\2\4?\3\2\2\2\6Z\3\2")
        buf.write("\2\2\b\\\3\2\2\2\n^\3\2\2\2\f`\3\2\2\2\16\17\5\4\3\2\17")
        buf.write("\20\7\2\2\3\20\3\3\2\2\2\21\22\b\3\1\2\22@\7\33\2\2\23")
        buf.write("@\7\34\2\2\24@\7\30\2\2\25@\7\27\2\2\26@\t\2\2\2\27\30")
        buf.write("\5\6\4\2\30\31\5\4\3\17\31@\3\2\2\2\32\33\7\21\2\2\33")
        buf.write("\34\5\4\3\2\34\35\7\22\2\2\35@\3\2\2\2\36\37\7\b\2\2\37")
        buf.write(" \7\21\2\2 !\5\n\6\2!\"\7\22\2\2\"@\3\2\2\2#$\7\t\2\2")
        buf.write("$%\7\21\2\2%&\7\30\2\2&@\7\22\2\2\'(\7\n\2\2()\7\21\2")
        buf.write("\2)*\5\n\6\2*,\7\13\2\2+-\7\5\2\2,+\3\2\2\2,-\3\2\2\2")
        buf.write("-.\3\2\2\2./\5\n\6\2/\60\7\22\2\2\60@\3\2\2\2\61\62\5")
        buf.write("\b\5\2\62;\7\21\2\2\638\5\4\3\2\64\65\7\13\2\2\65\67\5")
        buf.write("\4\3\2\66\64\3\2\2\2\67:\3\2\2\28\66\3\2\2\289\3\2\2\2")
        buf.write("9<\3\2\2\2:8\3\2\2\2;\63\3\2\2\2;<\3\2\2\2<=\3\2\2\2=")
        buf.write(">\7\22\2\2>@\3\2\2\2?\21\3\2\2\2?\23\3\2\2\2?\24\3\2\2")
        buf.write("\2?\25\3\2\2\2?\26\3\2\2\2?\27\3\2\2\2?\32\3\2\2\2?\36")
        buf.write("\3\2\2\2?#\3\2\2\2?\'\3\2\2\2?\61\3\2\2\2@W\3\2\2\2AB")
        buf.write("\f\f\2\2BC\t\3\2\2CV\5\4\3\rDE\f\13\2\2EF\t\4\2\2FV\5")
        buf.write("\4\3\fGH\f\n\2\2HI\t\5\2\2IV\5\4\3\13JK\f\t\2\2KL\t\6")
        buf.write("\2\2LV\5\4\3\nMN\f\b\2\2NO\7 \2\2OV\5\4\3\tPQ\f\7\2\2")
        buf.write("QR\7B\2\2RV\5\4\3\bST\f\16\2\2TV\5\6\4\2UA\3\2\2\2UD\3")
        buf.write("\2\2\2UG\3\2\2\2UJ\3\2\2\2UM\3\2\2\2UP\3\2\2\2US\3\2\2")
        buf.write("\2VY\3\2\2\2WU\3\2\2\2WX\3\2\2\2X\5\3\2\2\2YW\3\2\2\2")
        buf.write("Z[\t\7\2\2[\7\3\2\2\2\\]\5\f\7\2]\t\3\2\2\2^_\t\b\2\2")
        buf.write("_\13\3\2\2\2`a\t\t\2\2a\r\3\2\2\2\b,8;?UW")
        return buf.getvalue()


class BaserowFormula ( Parser ):

    grammarFileName = "BaserowFormula.g4"

    atn = ATNDeserializer().deserialize(serializedATN())

    decisionsToDFA = [ DFA(ds, i) for i, ds in enumerate(atn.decisionToState) ]

    sharedContextCache = PredictionContextCache()

    literalNames = [ "<INVALID>", "<INVALID>", "<INVALID>", "<INVALID>", 
                     "<INVALID>", "<INVALID>", "<INVALID>", "<INVALID>", 
                     "<INVALID>", "','", "':'", "'::'", "'$'", "'$$'", "'*'", 
                     "'('", "')'", "'['", "']'", "<INVALID>", "<INVALID>", 
                     "<INVALID>", "<INVALID>", "<INVALID>", "'.'", "<INVALID>", 
                     "<INVALID>", "<INVALID>", "<INVALID>", "'&'", "'&&'", 
                     "'&<'", "'@@'", "'@>'", "'@'", "'!'", "'!!'", "'!='", 
                     "'^'", "'='", "'=>'", "'>'", "'>='", "'>>'", "'#'", 
                     "'#='", "'#>'", "'#>>'", "'##'", "'->'", "'->>'", "'-|-'", 
                     "'<'", "'<='", "'<@'", "'<^'", "'<>'", "'<->'", "'<<'", 
                     "'<<='", "'<?>'", "'-'", "'%'", "'|'", "'||'", "'||/'", 
                     "'|/'", "'+'", "'?'", "'?&'", "'?#'", "'?-'", "'?|'", 
                     "'/'", "'~'", "'~='", "'~>=~'", "'~>~'", "'~<=~'", 
                     "'~<~'", "'~*'", "'~~'", "';'" ]

    symbolicNames = [ "<INVALID>", "BLOCK_COMMENT", "LINE_COMMENT", "WHITESPACE", 
                      "TRUE", "FALSE", "FIELD", "FIELDBYID", "LOOKUP", "COMMA", 
                      "COLON", "COLON_COLON", "DOLLAR", "DOLLAR_DOLLAR", 
                      "STAR", "OPEN_PAREN", "CLOSE_PAREN", "OPEN_BRACKET", 
                      "CLOSE_BRACKET", "BIT_STRING", "REGEX_STRING", "NUMERIC_LITERAL", 
                      "INTEGER_LITERAL", "HEX_INTEGER_LITERAL", "DOT", "SINGLEQ_STRING_LITERAL", 
                      "DOUBLEQ_STRING_LITERAL", "IDENTIFIER", "IDENTIFIER_UNICODE", 
                      "AMP", "AMP_AMP", "AMP_LT", "AT_AT", "AT_GT", "AT_SIGN", 
                      "BANG", "BANG_BANG", "BANG_EQUAL", "CARET", "EQUAL", 
                      "EQUAL_GT", "GT", "GTE", "GT_GT", "HASH", "HASH_EQ", 
                      "HASH_GT", "HASH_GT_GT", "HASH_HASH", "HYPHEN_GT", 
                      "HYPHEN_GT_GT", "HYPHEN_PIPE_HYPHEN", "LT", "LTE", 
                      "LT_AT", "LT_CARET", "LT_GT", "LT_HYPHEN_GT", "LT_LT", 
                      "LT_LT_EQ", "LT_QMARK_GT", "MINUS", "PERCENT", "PIPE", 
                      "PIPE_PIPE", "PIPE_PIPE_SLASH", "PIPE_SLASH", "PLUS", 
                      "QMARK", "QMARK_AMP", "QMARK_HASH", "QMARK_HYPHEN", 
                      "QMARK_PIPE", "SLASH", "TIL", "TIL_EQ", "TIL_GTE_TIL", 
                      "TIL_GT_TIL", "TIL_LTE_TIL", "TIL_LT_TIL", "TIL_STAR", 
                      "TIL_TIL", "SEMI", "ErrorCharacter" ]

    RULE_root = 0
    RULE_expr = 1
    RULE_ws_or_comment = 2
    RULE_func_name = 3
    RULE_field_reference = 4
    RULE_identifier = 5

    ruleNames =  [ "root", "expr", "ws_or_comment", "func_name", "field_reference", 
                   "identifier" ]

    EOF = Token.EOF
    BLOCK_COMMENT=1
    LINE_COMMENT=2
    WHITESPACE=3
    TRUE=4
    FALSE=5
    FIELD=6
    FIELDBYID=7
    LOOKUP=8
    COMMA=9
    COLON=10
    COLON_COLON=11
    DOLLAR=12
    DOLLAR_DOLLAR=13
    STAR=14
    OPEN_PAREN=15
    CLOSE_PAREN=16
    OPEN_BRACKET=17
    CLOSE_BRACKET=18
    BIT_STRING=19
    REGEX_STRING=20
    NUMERIC_LITERAL=21
    INTEGER_LITERAL=22
    HEX_INTEGER_LITERAL=23
    DOT=24
    SINGLEQ_STRING_LITERAL=25
    DOUBLEQ_STRING_LITERAL=26
    IDENTIFIER=27
    IDENTIFIER_UNICODE=28
    AMP=29
    AMP_AMP=30
    AMP_LT=31
    AT_AT=32
    AT_GT=33
    AT_SIGN=34
    BANG=35
    BANG_BANG=36
    BANG_EQUAL=37
    CARET=38
    EQUAL=39
    EQUAL_GT=40
    GT=41
    GTE=42
    GT_GT=43
    HASH=44
    HASH_EQ=45
    HASH_GT=46
    HASH_GT_GT=47
    HASH_HASH=48
    HYPHEN_GT=49
    HYPHEN_GT_GT=50
    HYPHEN_PIPE_HYPHEN=51
    LT=52
    LTE=53
    LT_AT=54
    LT_CARET=55
    LT_GT=56
    LT_HYPHEN_GT=57
    LT_LT=58
    LT_LT_EQ=59
    LT_QMARK_GT=60
    MINUS=61
    PERCENT=62
    PIPE=63
    PIPE_PIPE=64
    PIPE_PIPE_SLASH=65
    PIPE_SLASH=66
    PLUS=67
    QMARK=68
    QMARK_AMP=69
    QMARK_HASH=70
    QMARK_HYPHEN=71
    QMARK_PIPE=72
    SLASH=73
    TIL=74
    TIL_EQ=75
    TIL_GTE_TIL=76
    TIL_GT_TIL=77
    TIL_LTE_TIL=78
    TIL_LT_TIL=79
    TIL_STAR=80
    TIL_TIL=81
    SEMI=82
    ErrorCharacter=83

    def __init__(self, input:TokenStream, output:TextIO = sys.stdout):
        super().__init__(input, output)
        self.checkVersion("4.9")
        self._interp = ParserATNSimulator(self, self.atn, self.decisionsToDFA, self.sharedContextCache)
        self._predicates = None




    class RootContext(ParserRuleContext):

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def expr(self):
            return self.getTypedRuleContext(BaserowFormula.ExprContext,0)


        def EOF(self):
            return self.getToken(BaserowFormula.EOF, 0)

        def getRuleIndex(self):
            return BaserowFormula.RULE_root

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterRoot" ):
                listener.enterRoot(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitRoot" ):
                listener.exitRoot(self)

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitRoot" ):
                return visitor.visitRoot(self)
            else:
                return visitor.visitChildren(self)




    def root(self):

        localctx = BaserowFormula.RootContext(self, self._ctx, self.state)
        self.enterRule(localctx, 0, self.RULE_root)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 12
            self.expr(0)
            self.state = 13
            self.match(BaserowFormula.EOF)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class ExprContext(ParserRuleContext):

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser


        def getRuleIndex(self):
            return BaserowFormula.RULE_expr

     
        def copyFrom(self, ctx:ParserRuleContext):
            super().copyFrom(ctx)


    class FieldReferenceContext(ExprContext):

        def __init__(self, parser, ctx:ParserRuleContext): # actually a BaserowFormula.ExprContext
            super().__init__(parser)
            self.copyFrom(ctx)

        def FIELD(self):
            return self.getToken(BaserowFormula.FIELD, 0)
        def OPEN_PAREN(self):
            return self.getToken(BaserowFormula.OPEN_PAREN, 0)
        def field_reference(self):
            return self.getTypedRuleContext(BaserowFormula.Field_referenceContext,0)

        def CLOSE_PAREN(self):
            return self.getToken(BaserowFormula.CLOSE_PAREN, 0)

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterFieldReference" ):
                listener.enterFieldReference(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitFieldReference" ):
                listener.exitFieldReference(self)

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitFieldReference" ):
                return visitor.visitFieldReference(self)
            else:
                return visitor.visitChildren(self)


    class StringLiteralContext(ExprContext):

        def __init__(self, parser, ctx:ParserRuleContext): # actually a BaserowFormula.ExprContext
            super().__init__(parser)
            self.copyFrom(ctx)

        def SINGLEQ_STRING_LITERAL(self):
            return self.getToken(BaserowFormula.SINGLEQ_STRING_LITERAL, 0)
        def DOUBLEQ_STRING_LITERAL(self):
            return self.getToken(BaserowFormula.DOUBLEQ_STRING_LITERAL, 0)

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterStringLiteral" ):
                listener.enterStringLiteral(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitStringLiteral" ):
                listener.exitStringLiteral(self)

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitStringLiteral" ):
                return visitor.visitStringLiteral(self)
            else:
                return visitor.visitChildren(self)


    class BracketsContext(ExprContext):

        def __init__(self, parser, ctx:ParserRuleContext): # actually a BaserowFormula.ExprContext
            super().__init__(parser)
            self.copyFrom(ctx)

        def OPEN_PAREN(self):
            return self.getToken(BaserowFormula.OPEN_PAREN, 0)
        def expr(self):
            return self.getTypedRuleContext(BaserowFormula.ExprContext,0)

        def CLOSE_PAREN(self):
            return self.getToken(BaserowFormula.CLOSE_PAREN, 0)

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterBrackets" ):
                listener.enterBrackets(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitBrackets" ):
                listener.exitBrackets(self)

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitBrackets" ):
                return visitor.visitBrackets(self)
            else:
                return visitor.visitChildren(self)


    class BooleanLiteralContext(ExprContext):

        def __init__(self, parser, ctx:ParserRuleContext): # actually a BaserowFormula.ExprContext
            super().__init__(parser)
            self.copyFrom(ctx)

        def TRUE(self):
            return self.getToken(BaserowFormula.TRUE, 0)
        def FALSE(self):
            return self.getToken(BaserowFormula.FALSE, 0)

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterBooleanLiteral" ):
                listener.enterBooleanLiteral(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitBooleanLiteral" ):
                listener.exitBooleanLiteral(self)

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitBooleanLiteral" ):
                return visitor.visitBooleanLiteral(self)
            else:
                return visitor.visitChildren(self)


    class RightWhitespaceOrCommentsContext(ExprContext):

        def __init__(self, parser, ctx:ParserRuleContext): # actually a BaserowFormula.ExprContext
            super().__init__(parser)
            self.copyFrom(ctx)

        def expr(self):
            return self.getTypedRuleContext(BaserowFormula.ExprContext,0)

        def ws_or_comment(self):
            return self.getTypedRuleContext(BaserowFormula.Ws_or_commentContext,0)


        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterRightWhitespaceOrComments" ):
                listener.enterRightWhitespaceOrComments(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitRightWhitespaceOrComments" ):
                listener.exitRightWhitespaceOrComments(self)

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitRightWhitespaceOrComments" ):
                return visitor.visitRightWhitespaceOrComments(self)
            else:
                return visitor.visitChildren(self)


    class DecimalLiteralContext(ExprContext):

        def __init__(self, parser, ctx:ParserRuleContext): # actually a BaserowFormula.ExprContext
            super().__init__(parser)
            self.copyFrom(ctx)

        def NUMERIC_LITERAL(self):
            return self.getToken(BaserowFormula.NUMERIC_LITERAL, 0)

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterDecimalLiteral" ):
                listener.enterDecimalLiteral(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitDecimalLiteral" ):
                listener.exitDecimalLiteral(self)

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitDecimalLiteral" ):
                return visitor.visitDecimalLiteral(self)
            else:
                return visitor.visitChildren(self)


    class LeftWhitespaceOrCommentsContext(ExprContext):

        def __init__(self, parser, ctx:ParserRuleContext): # actually a BaserowFormula.ExprContext
            super().__init__(parser)
            self.copyFrom(ctx)

        def ws_or_comment(self):
            return self.getTypedRuleContext(BaserowFormula.Ws_or_commentContext,0)

        def expr(self):
            return self.getTypedRuleContext(BaserowFormula.ExprContext,0)


        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterLeftWhitespaceOrComments" ):
                listener.enterLeftWhitespaceOrComments(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitLeftWhitespaceOrComments" ):
                listener.exitLeftWhitespaceOrComments(self)

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitLeftWhitespaceOrComments" ):
                return visitor.visitLeftWhitespaceOrComments(self)
            else:
                return visitor.visitChildren(self)


    class FunctionCallContext(ExprContext):

        def __init__(self, parser, ctx:ParserRuleContext): # actually a BaserowFormula.ExprContext
            super().__init__(parser)
            self.copyFrom(ctx)

        def func_name(self):
            return self.getTypedRuleContext(BaserowFormula.Func_nameContext,0)

        def OPEN_PAREN(self):
            return self.getToken(BaserowFormula.OPEN_PAREN, 0)
        def CLOSE_PAREN(self):
            return self.getToken(BaserowFormula.CLOSE_PAREN, 0)
        def expr(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(BaserowFormula.ExprContext)
            else:
                return self.getTypedRuleContext(BaserowFormula.ExprContext,i)

        def COMMA(self, i:int=None):
            if i is None:
                return self.getTokens(BaserowFormula.COMMA)
            else:
                return self.getToken(BaserowFormula.COMMA, i)

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterFunctionCall" ):
                listener.enterFunctionCall(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitFunctionCall" ):
                listener.exitFunctionCall(self)

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitFunctionCall" ):
                return visitor.visitFunctionCall(self)
            else:
                return visitor.visitChildren(self)


    class FieldByIdReferenceContext(ExprContext):

        def __init__(self, parser, ctx:ParserRuleContext): # actually a BaserowFormula.ExprContext
            super().__init__(parser)
            self.copyFrom(ctx)

        def FIELDBYID(self):
            return self.getToken(BaserowFormula.FIELDBYID, 0)
        def OPEN_PAREN(self):
            return self.getToken(BaserowFormula.OPEN_PAREN, 0)
        def INTEGER_LITERAL(self):
            return self.getToken(BaserowFormula.INTEGER_LITERAL, 0)
        def CLOSE_PAREN(self):
            return self.getToken(BaserowFormula.CLOSE_PAREN, 0)

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterFieldByIdReference" ):
                listener.enterFieldByIdReference(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitFieldByIdReference" ):
                listener.exitFieldByIdReference(self)

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitFieldByIdReference" ):
                return visitor.visitFieldByIdReference(self)
            else:
                return visitor.visitChildren(self)


    class LookupFieldReferenceContext(ExprContext):

        def __init__(self, parser, ctx:ParserRuleContext): # actually a BaserowFormula.ExprContext
            super().__init__(parser)
            self.copyFrom(ctx)

        def LOOKUP(self):
            return self.getToken(BaserowFormula.LOOKUP, 0)
        def OPEN_PAREN(self):
            return self.getToken(BaserowFormula.OPEN_PAREN, 0)
        def field_reference(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(BaserowFormula.Field_referenceContext)
            else:
                return self.getTypedRuleContext(BaserowFormula.Field_referenceContext,i)

        def COMMA(self):
            return self.getToken(BaserowFormula.COMMA, 0)
        def CLOSE_PAREN(self):
            return self.getToken(BaserowFormula.CLOSE_PAREN, 0)
        def WHITESPACE(self):
            return self.getToken(BaserowFormula.WHITESPACE, 0)

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterLookupFieldReference" ):
                listener.enterLookupFieldReference(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitLookupFieldReference" ):
                listener.exitLookupFieldReference(self)

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitLookupFieldReference" ):
                return visitor.visitLookupFieldReference(self)
            else:
                return visitor.visitChildren(self)


    class IntegerLiteralContext(ExprContext):

        def __init__(self, parser, ctx:ParserRuleContext): # actually a BaserowFormula.ExprContext
            super().__init__(parser)
            self.copyFrom(ctx)

        def INTEGER_LITERAL(self):
            return self.getToken(BaserowFormula.INTEGER_LITERAL, 0)

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterIntegerLiteral" ):
                listener.enterIntegerLiteral(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitIntegerLiteral" ):
                listener.exitIntegerLiteral(self)

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitIntegerLiteral" ):
                return visitor.visitIntegerLiteral(self)
            else:
                return visitor.visitChildren(self)


    class BinaryOpContext(ExprContext):

        def __init__(self, parser, ctx:ParserRuleContext): # actually a BaserowFormula.ExprContext
            super().__init__(parser)
            self.op = None # Token
            self.copyFrom(ctx)

        def expr(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(BaserowFormula.ExprContext)
            else:
                return self.getTypedRuleContext(BaserowFormula.ExprContext,i)

        def SLASH(self):
            return self.getToken(BaserowFormula.SLASH, 0)
        def STAR(self):
            return self.getToken(BaserowFormula.STAR, 0)
        def PLUS(self):
            return self.getToken(BaserowFormula.PLUS, 0)
        def MINUS(self):
            return self.getToken(BaserowFormula.MINUS, 0)
        def GT(self):
            return self.getToken(BaserowFormula.GT, 0)
        def LT(self):
            return self.getToken(BaserowFormula.LT, 0)
        def GTE(self):
            return self.getToken(BaserowFormula.GTE, 0)
        def LTE(self):
            return self.getToken(BaserowFormula.LTE, 0)
        def EQUAL(self):
            return self.getToken(BaserowFormula.EQUAL, 0)
        def BANG_EQUAL(self):
            return self.getToken(BaserowFormula.BANG_EQUAL, 0)
        def AMP_AMP(self):
            return self.getToken(BaserowFormula.AMP_AMP, 0)
        def PIPE_PIPE(self):
            return self.getToken(BaserowFormula.PIPE_PIPE, 0)

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterBinaryOp" ):
                listener.enterBinaryOp(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitBinaryOp" ):
                listener.exitBinaryOp(self)

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitBinaryOp" ):
                return visitor.visitBinaryOp(self)
            else:
                return visitor.visitChildren(self)



    def expr(self, _p:int=0):
        _parentctx = self._ctx
        _parentState = self.state
        localctx = BaserowFormula.ExprContext(self, self._ctx, _parentState)
        _prevctx = localctx
        _startState = 2
        self.enterRecursionRule(localctx, 2, self.RULE_expr, _p)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 61
            self._errHandler.sync(self)
            token = self._input.LA(1)
            if token in [BaserowFormula.SINGLEQ_STRING_LITERAL]:
                localctx = BaserowFormula.StringLiteralContext(self, localctx)
                self._ctx = localctx
                _prevctx = localctx

                self.state = 16
                self.match(BaserowFormula.SINGLEQ_STRING_LITERAL)
                pass
            elif token in [BaserowFormula.DOUBLEQ_STRING_LITERAL]:
                localctx = BaserowFormula.StringLiteralContext(self, localctx)
                self._ctx = localctx
                _prevctx = localctx
                self.state = 17
                self.match(BaserowFormula.DOUBLEQ_STRING_LITERAL)
                pass
            elif token in [BaserowFormula.INTEGER_LITERAL]:
                localctx = BaserowFormula.IntegerLiteralContext(self, localctx)
                self._ctx = localctx
                _prevctx = localctx
                self.state = 18
                self.match(BaserowFormula.INTEGER_LITERAL)
                pass
            elif token in [BaserowFormula.NUMERIC_LITERAL]:
                localctx = BaserowFormula.DecimalLiteralContext(self, localctx)
                self._ctx = localctx
                _prevctx = localctx
                self.state = 19
                self.match(BaserowFormula.NUMERIC_LITERAL)
                pass
            elif token in [BaserowFormula.TRUE, BaserowFormula.FALSE]:
                localctx = BaserowFormula.BooleanLiteralContext(self, localctx)
                self._ctx = localctx
                _prevctx = localctx
                self.state = 20
                _la = self._input.LA(1)
                if not(_la==BaserowFormula.TRUE or _la==BaserowFormula.FALSE):
                    self._errHandler.recoverInline(self)
                else:
                    self._errHandler.reportMatch(self)
                    self.consume()
                pass
            elif token in [BaserowFormula.BLOCK_COMMENT, BaserowFormula.LINE_COMMENT, BaserowFormula.WHITESPACE]:
                localctx = BaserowFormula.LeftWhitespaceOrCommentsContext(self, localctx)
                self._ctx = localctx
                _prevctx = localctx
                self.state = 21
                self.ws_or_comment()
                self.state = 22
                self.expr(13)
                pass
            elif token in [BaserowFormula.OPEN_PAREN]:
                localctx = BaserowFormula.BracketsContext(self, localctx)
                self._ctx = localctx
                _prevctx = localctx
                self.state = 24
                self.match(BaserowFormula.OPEN_PAREN)
                self.state = 25
                self.expr(0)
                self.state = 26
                self.match(BaserowFormula.CLOSE_PAREN)
                pass
            elif token in [BaserowFormula.FIELD]:
                localctx = BaserowFormula.FieldReferenceContext(self, localctx)
                self._ctx = localctx
                _prevctx = localctx
                self.state = 28
                self.match(BaserowFormula.FIELD)
                self.state = 29
                self.match(BaserowFormula.OPEN_PAREN)
                self.state = 30
                self.field_reference()
                self.state = 31
                self.match(BaserowFormula.CLOSE_PAREN)
                pass
            elif token in [BaserowFormula.FIELDBYID]:
                localctx = BaserowFormula.FieldByIdReferenceContext(self, localctx)
                self._ctx = localctx
                _prevctx = localctx
                self.state = 33
                self.match(BaserowFormula.FIELDBYID)
                self.state = 34
                self.match(BaserowFormula.OPEN_PAREN)
                self.state = 35
                self.match(BaserowFormula.INTEGER_LITERAL)
                self.state = 36
                self.match(BaserowFormula.CLOSE_PAREN)
                pass
            elif token in [BaserowFormula.LOOKUP]:
                localctx = BaserowFormula.LookupFieldReferenceContext(self, localctx)
                self._ctx = localctx
                _prevctx = localctx
                self.state = 37
                self.match(BaserowFormula.LOOKUP)
                self.state = 38
                self.match(BaserowFormula.OPEN_PAREN)
                self.state = 39
                self.field_reference()
                self.state = 40
                self.match(BaserowFormula.COMMA)
                self.state = 42
                self._errHandler.sync(self)
                _la = self._input.LA(1)
                if _la==BaserowFormula.WHITESPACE:
                    self.state = 41
                    self.match(BaserowFormula.WHITESPACE)


                self.state = 44
                self.field_reference()
                self.state = 45
                self.match(BaserowFormula.CLOSE_PAREN)
                pass
            elif token in [BaserowFormula.IDENTIFIER, BaserowFormula.IDENTIFIER_UNICODE]:
                localctx = BaserowFormula.FunctionCallContext(self, localctx)
                self._ctx = localctx
                _prevctx = localctx
                self.state = 47
                self.func_name()
                self.state = 48
                self.match(BaserowFormula.OPEN_PAREN)
                self.state = 57
                self._errHandler.sync(self)
                _la = self._input.LA(1)
                if (((_la) & ~0x3f) == 0 and ((1 << _la) & ((1 << BaserowFormula.BLOCK_COMMENT) | (1 << BaserowFormula.LINE_COMMENT) | (1 << BaserowFormula.WHITESPACE) | (1 << BaserowFormula.TRUE) | (1 << BaserowFormula.FALSE) | (1 << BaserowFormula.FIELD) | (1 << BaserowFormula.FIELDBYID) | (1 << BaserowFormula.LOOKUP) | (1 << BaserowFormula.OPEN_PAREN) | (1 << BaserowFormula.NUMERIC_LITERAL) | (1 << BaserowFormula.INTEGER_LITERAL) | (1 << BaserowFormula.SINGLEQ_STRING_LITERAL) | (1 << BaserowFormula.DOUBLEQ_STRING_LITERAL) | (1 << BaserowFormula.IDENTIFIER) | (1 << BaserowFormula.IDENTIFIER_UNICODE))) != 0):
                    self.state = 49
                    self.expr(0)
                    self.state = 54
                    self._errHandler.sync(self)
                    _la = self._input.LA(1)
                    while _la==BaserowFormula.COMMA:
                        self.state = 50
                        self.match(BaserowFormula.COMMA)
                        self.state = 51
                        self.expr(0)
                        self.state = 56
                        self._errHandler.sync(self)
                        _la = self._input.LA(1)



                self.state = 59
                self.match(BaserowFormula.CLOSE_PAREN)
                pass
            else:
                raise NoViableAltException(self)

            self._ctx.stop = self._input.LT(-1)
            self.state = 85
            self._errHandler.sync(self)
            _alt = self._interp.adaptivePredict(self._input,5,self._ctx)
            while _alt!=2 and _alt!=ATN.INVALID_ALT_NUMBER:
                if _alt==1:
                    if self._parseListeners is not None:
                        self.triggerExitRuleEvent()
                    _prevctx = localctx
                    self.state = 83
                    self._errHandler.sync(self)
                    la_ = self._interp.adaptivePredict(self._input,4,self._ctx)
                    if la_ == 1:
                        localctx = BaserowFormula.BinaryOpContext(self, BaserowFormula.ExprContext(self, _parentctx, _parentState))
                        self.pushNewRecursionContext(localctx, _startState, self.RULE_expr)
                        self.state = 63
                        if not self.precpred(self._ctx, 10):
                            from antlr4.error.Errors import FailedPredicateException
                            raise FailedPredicateException(self, "self.precpred(self._ctx, 10)")
                        self.state = 64
                        localctx.op = self._input.LT(1)
                        _la = self._input.LA(1)
                        if not(_la==BaserowFormula.STAR or _la==BaserowFormula.SLASH):
                            localctx.op = self._errHandler.recoverInline(self)
                        else:
                            self._errHandler.reportMatch(self)
                            self.consume()
                        self.state = 65
                        self.expr(11)
                        pass

                    elif la_ == 2:
                        localctx = BaserowFormula.BinaryOpContext(self, BaserowFormula.ExprContext(self, _parentctx, _parentState))
                        self.pushNewRecursionContext(localctx, _startState, self.RULE_expr)
                        self.state = 66
                        if not self.precpred(self._ctx, 9):
                            from antlr4.error.Errors import FailedPredicateException
                            raise FailedPredicateException(self, "self.precpred(self._ctx, 9)")
                        self.state = 67
                        localctx.op = self._input.LT(1)
                        _la = self._input.LA(1)
                        if not(_la==BaserowFormula.MINUS or _la==BaserowFormula.PLUS):
                            localctx.op = self._errHandler.recoverInline(self)
                        else:
                            self._errHandler.reportMatch(self)
                            self.consume()
                        self.state = 68
                        self.expr(10)
                        pass

                    elif la_ == 3:
                        localctx = BaserowFormula.BinaryOpContext(self, BaserowFormula.ExprContext(self, _parentctx, _parentState))
                        self.pushNewRecursionContext(localctx, _startState, self.RULE_expr)
                        self.state = 69
                        if not self.precpred(self._ctx, 8):
                            from antlr4.error.Errors import FailedPredicateException
                            raise FailedPredicateException(self, "self.precpred(self._ctx, 8)")
                        self.state = 70
                        localctx.op = self._input.LT(1)
                        _la = self._input.LA(1)
                        if not((((_la) & ~0x3f) == 0 and ((1 << _la) & ((1 << BaserowFormula.GT) | (1 << BaserowFormula.GTE) | (1 << BaserowFormula.LT) | (1 << BaserowFormula.LTE))) != 0)):
                            localctx.op = self._errHandler.recoverInline(self)
                        else:
                            self._errHandler.reportMatch(self)
                            self.consume()
                        self.state = 71
                        self.expr(9)
                        pass

                    elif la_ == 4:
                        localctx = BaserowFormula.BinaryOpContext(self, BaserowFormula.ExprContext(self, _parentctx, _parentState))
                        self.pushNewRecursionContext(localctx, _startState, self.RULE_expr)
                        self.state = 72
                        if not self.precpred(self._ctx, 7):
                            from antlr4.error.Errors import FailedPredicateException
                            raise FailedPredicateException(self, "self.precpred(self._ctx, 7)")
                        self.state = 73
                        localctx.op = self._input.LT(1)
                        _la = self._input.LA(1)
                        if not(_la==BaserowFormula.BANG_EQUAL or _la==BaserowFormula.EQUAL):
                            localctx.op = self._errHandler.recoverInline(self)
                        else:
                            self._errHandler.reportMatch(self)
                            self.consume()
                        self.state = 74
                        self.expr(8)
                        pass

                    elif la_ == 5:
                        localctx = BaserowFormula.BinaryOpContext(self, BaserowFormula.ExprContext(self, _parentctx, _parentState))
                        self.pushNewRecursionContext(localctx, _startState, self.RULE_expr)
                        self.state = 75
                        if not self.precpred(self._ctx, 6):
                            from antlr4.error.Errors import FailedPredicateException
                            raise FailedPredicateException(self, "self.precpred(self._ctx, 6)")
                        self.state = 76
                        localctx.op = self.match(BaserowFormula.AMP_AMP)
                        self.state = 77
                        self.expr(7)
                        pass

                    elif la_ == 6:
                        localctx = BaserowFormula.BinaryOpContext(self, BaserowFormula.ExprContext(self, _parentctx, _parentState))
                        self.pushNewRecursionContext(localctx, _startState, self.RULE_expr)
                        self.state = 78
                        if not self.precpred(self._ctx, 5):
                            from antlr4.error.Errors import FailedPredicateException
                            raise FailedPredicateException(self, "self.precpred(self._ctx, 5)")
                        self.state = 79
                        localctx.op = self.match(BaserowFormula.PIPE_PIPE)
                        self.state = 80
                        self.expr(6)
                        pass

                    elif la_ == 7:
                        localctx = BaserowFormula.RightWhitespaceOrCommentsContext(self, BaserowFormula.ExprContext(self, _parentctx, _parentState))
                        self.pushNewRecursionContext(localctx, _startState, self.RULE_expr)
                        self.state = 81
                        if not self.precpred(self._ctx, 12):
                            from antlr4.error.Errors import FailedPredicateException
                            raise FailedPredicateException(self, "self.precpred(self._ctx, 12)")
                        self.state = 82
                        self.ws_or_comment()
                        pass

             
                self.state = 87
                self._errHandler.sync(self)
                _alt = self._interp.adaptivePredict(self._input,5,self._ctx)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.unrollRecursionContexts(_parentctx)
        return localctx


    class Ws_or_commentContext(ParserRuleContext):

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def BLOCK_COMMENT(self):
            return self.getToken(BaserowFormula.BLOCK_COMMENT, 0)

        def LINE_COMMENT(self):
            return self.getToken(BaserowFormula.LINE_COMMENT, 0)

        def WHITESPACE(self):
            return self.getToken(BaserowFormula.WHITESPACE, 0)

        def getRuleIndex(self):
            return BaserowFormula.RULE_ws_or_comment

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterWs_or_comment" ):
                listener.enterWs_or_comment(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitWs_or_comment" ):
                listener.exitWs_or_comment(self)

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitWs_or_comment" ):
                return visitor.visitWs_or_comment(self)
            else:
                return visitor.visitChildren(self)




    def ws_or_comment(self):

        localctx = BaserowFormula.Ws_or_commentContext(self, self._ctx, self.state)
        self.enterRule(localctx, 4, self.RULE_ws_or_comment)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 88
            _la = self._input.LA(1)
            if not((((_la) & ~0x3f) == 0 and ((1 << _la) & ((1 << BaserowFormula.BLOCK_COMMENT) | (1 << BaserowFormula.LINE_COMMENT) | (1 << BaserowFormula.WHITESPACE))) != 0)):
                self._errHandler.recoverInline(self)
            else:
                self._errHandler.reportMatch(self)
                self.consume()
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class Func_nameContext(ParserRuleContext):

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def identifier(self):
            return self.getTypedRuleContext(BaserowFormula.IdentifierContext,0)


        def getRuleIndex(self):
            return BaserowFormula.RULE_func_name

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterFunc_name" ):
                listener.enterFunc_name(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitFunc_name" ):
                listener.exitFunc_name(self)

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitFunc_name" ):
                return visitor.visitFunc_name(self)
            else:
                return visitor.visitChildren(self)




    def func_name(self):

        localctx = BaserowFormula.Func_nameContext(self, self._ctx, self.state)
        self.enterRule(localctx, 6, self.RULE_func_name)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 90
            self.identifier()
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class Field_referenceContext(ParserRuleContext):

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def SINGLEQ_STRING_LITERAL(self):
            return self.getToken(BaserowFormula.SINGLEQ_STRING_LITERAL, 0)

        def DOUBLEQ_STRING_LITERAL(self):
            return self.getToken(BaserowFormula.DOUBLEQ_STRING_LITERAL, 0)

        def getRuleIndex(self):
            return BaserowFormula.RULE_field_reference

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterField_reference" ):
                listener.enterField_reference(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitField_reference" ):
                listener.exitField_reference(self)

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitField_reference" ):
                return visitor.visitField_reference(self)
            else:
                return visitor.visitChildren(self)




    def field_reference(self):

        localctx = BaserowFormula.Field_referenceContext(self, self._ctx, self.state)
        self.enterRule(localctx, 8, self.RULE_field_reference)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 92
            _la = self._input.LA(1)
            if not(_la==BaserowFormula.SINGLEQ_STRING_LITERAL or _la==BaserowFormula.DOUBLEQ_STRING_LITERAL):
                self._errHandler.recoverInline(self)
            else:
                self._errHandler.reportMatch(self)
                self.consume()
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class IdentifierContext(ParserRuleContext):

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def IDENTIFIER(self):
            return self.getToken(BaserowFormula.IDENTIFIER, 0)

        def IDENTIFIER_UNICODE(self):
            return self.getToken(BaserowFormula.IDENTIFIER_UNICODE, 0)

        def getRuleIndex(self):
            return BaserowFormula.RULE_identifier

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterIdentifier" ):
                listener.enterIdentifier(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitIdentifier" ):
                listener.exitIdentifier(self)

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitIdentifier" ):
                return visitor.visitIdentifier(self)
            else:
                return visitor.visitChildren(self)




    def identifier(self):

        localctx = BaserowFormula.IdentifierContext(self, self._ctx, self.state)
        self.enterRule(localctx, 10, self.RULE_identifier)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 94
            _la = self._input.LA(1)
            if not(_la==BaserowFormula.IDENTIFIER or _la==BaserowFormula.IDENTIFIER_UNICODE):
                self._errHandler.recoverInline(self)
            else:
                self._errHandler.reportMatch(self)
                self.consume()
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx



    def sempred(self, localctx:RuleContext, ruleIndex:int, predIndex:int):
        if self._predicates == None:
            self._predicates = dict()
        self._predicates[1] = self.expr_sempred
        pred = self._predicates.get(ruleIndex, None)
        if pred is None:
            raise Exception("No predicate with index:" + str(ruleIndex))
        else:
            return pred(localctx, predIndex)

    def expr_sempred(self, localctx:ExprContext, predIndex:int):
            if predIndex == 0:
                return self.precpred(self._ctx, 10)
         

            if predIndex == 1:
                return self.precpred(self._ctx, 9)
         

            if predIndex == 2:
                return self.precpred(self._ctx, 8)
         

            if predIndex == 3:
                return self.precpred(self._ctx, 7)
         

            if predIndex == 4:
                return self.precpred(self._ctx, 6)
         

            if predIndex == 5:
                return self.precpred(self._ctx, 5)
         

            if predIndex == 6:
                return self.precpred(self._ctx, 12)
         




