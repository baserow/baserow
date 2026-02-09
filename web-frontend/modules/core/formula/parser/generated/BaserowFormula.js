// Generated from BaserowFormula.g4 by ANTLR 4.9
// jshint ignore: start
import antlr4 from 'antlr4';
import BaserowFormulaListener from './BaserowFormulaListener.js';
import BaserowFormulaVisitor from './BaserowFormulaVisitor.js';


const serializedATN = ["\u0003\u608b\ua72a\u8133\ub9ed\u417c\u3be7\u7786",
    "\u5964\u0003Uc\u0004\u0002\t\u0002\u0004\u0003\t\u0003\u0004\u0004\t",
    "\u0004\u0004\u0005\t\u0005\u0004\u0006\t\u0006\u0004\u0007\t\u0007\u0003",
    "\u0002\u0003\u0002\u0003\u0002\u0003\u0003\u0003\u0003\u0003\u0003\u0003",
    "\u0003\u0003\u0003\u0003\u0003\u0003\u0003\u0003\u0003\u0003\u0003\u0003",
    "\u0003\u0003\u0003\u0003\u0003\u0003\u0003\u0003\u0003\u0003\u0003\u0003",
    "\u0003\u0003\u0003\u0003\u0003\u0003\u0003\u0003\u0003\u0003\u0003\u0003",
    "\u0003\u0003\u0003\u0003\u0003\u0003\u0003\u0003\u0003\u0003\u0003\u0005",
    "\u0003-\n\u0003\u0003\u0003\u0003\u0003\u0003\u0003\u0003\u0003\u0003",
    "\u0003\u0003\u0003\u0003\u0003\u0003\u0003\u0007\u00037\n\u0003\f\u0003",
    "\u000e\u0003:\u000b\u0003\u0005\u0003<\n\u0003\u0003\u0003\u0003\u0003",
    "\u0005\u0003@\n\u0003\u0003\u0003\u0003\u0003\u0003\u0003\u0003\u0003",
    "\u0003\u0003\u0003\u0003\u0003\u0003\u0003\u0003\u0003\u0003\u0003\u0003",
    "\u0003\u0003\u0003\u0003\u0003\u0003\u0003\u0003\u0003\u0003\u0003\u0003",
    "\u0003\u0003\u0003\u0003\u0003\u0003\u0003\u0003\u0007\u0003V\n\u0003",
    "\f\u0003\u000e\u0003Y\u000b\u0003\u0003\u0004\u0003\u0004\u0003\u0005",
    "\u0003\u0005\u0003\u0006\u0003\u0006\u0003\u0007\u0003\u0007\u0003\u0007",
    "\u0002\u0003\u0004\b\u0002\u0004\u0006\b\n\f\u0002\n\u0003\u0002\u0006",
    "\u0007\u0004\u0002\u0010\u0010KK\u0004\u0002??EE\u0004\u0002+,67\u0004",
    "\u0002\'\'))\u0003\u0002\u0003\u0005\u0003\u0002\u001b\u001c\u0003\u0002",
    "\u001d\u001e\u0002p\u0002\u000e\u0003\u0002\u0002\u0002\u0004?\u0003",
    "\u0002\u0002\u0002\u0006Z\u0003\u0002\u0002\u0002\b\\\u0003\u0002\u0002",
    "\u0002\n^\u0003\u0002\u0002\u0002\f`\u0003\u0002\u0002\u0002\u000e\u000f",
    "\u0005\u0004\u0003\u0002\u000f\u0010\u0007\u0002\u0002\u0003\u0010\u0003",
    "\u0003\u0002\u0002\u0002\u0011\u0012\b\u0003\u0001\u0002\u0012@\u0007",
    "\u001b\u0002\u0002\u0013@\u0007\u001c\u0002\u0002\u0014@\u0007\u0018",
    "\u0002\u0002\u0015@\u0007\u0017\u0002\u0002\u0016@\t\u0002\u0002\u0002",
    "\u0017\u0018\u0005\u0006\u0004\u0002\u0018\u0019\u0005\u0004\u0003\u000f",
    "\u0019@\u0003\u0002\u0002\u0002\u001a\u001b\u0007\u0011\u0002\u0002",
    "\u001b\u001c\u0005\u0004\u0003\u0002\u001c\u001d\u0007\u0012\u0002\u0002",
    "\u001d@\u0003\u0002\u0002\u0002\u001e\u001f\u0007\b\u0002\u0002\u001f",
    " \u0007\u0011\u0002\u0002 !\u0005\n\u0006\u0002!\"\u0007\u0012\u0002",
    "\u0002\"@\u0003\u0002\u0002\u0002#$\u0007\t\u0002\u0002$%\u0007\u0011",
    "\u0002\u0002%&\u0007\u0018\u0002\u0002&@\u0007\u0012\u0002\u0002\'(",
    "\u0007\n\u0002\u0002()\u0007\u0011\u0002\u0002)*\u0005\n\u0006\u0002",
    "*,\u0007\u000b\u0002\u0002+-\u0007\u0005\u0002\u0002,+\u0003\u0002\u0002",
    "\u0002,-\u0003\u0002\u0002\u0002-.\u0003\u0002\u0002\u0002./\u0005\n",
    "\u0006\u0002/0\u0007\u0012\u0002\u00020@\u0003\u0002\u0002\u000212\u0005",
    "\b\u0005\u00022;\u0007\u0011\u0002\u000238\u0005\u0004\u0003\u00024",
    "5\u0007\u000b\u0002\u000257\u0005\u0004\u0003\u000264\u0003\u0002\u0002",
    "\u00027:\u0003\u0002\u0002\u000286\u0003\u0002\u0002\u000289\u0003\u0002",
    "\u0002\u00029<\u0003\u0002\u0002\u0002:8\u0003\u0002\u0002\u0002;3\u0003",
    "\u0002\u0002\u0002;<\u0003\u0002\u0002\u0002<=\u0003\u0002\u0002\u0002",
    "=>\u0007\u0012\u0002\u0002>@\u0003\u0002\u0002\u0002?\u0011\u0003\u0002",
    "\u0002\u0002?\u0013\u0003\u0002\u0002\u0002?\u0014\u0003\u0002\u0002",
    "\u0002?\u0015\u0003\u0002\u0002\u0002?\u0016\u0003\u0002\u0002\u0002",
    "?\u0017\u0003\u0002\u0002\u0002?\u001a\u0003\u0002\u0002\u0002?\u001e",
    "\u0003\u0002\u0002\u0002?#\u0003\u0002\u0002\u0002?\'\u0003\u0002\u0002",
    "\u0002?1\u0003\u0002\u0002\u0002@W\u0003\u0002\u0002\u0002AB\f\f\u0002",
    "\u0002BC\t\u0003\u0002\u0002CV\u0005\u0004\u0003\rDE\f\u000b\u0002\u0002",
    "EF\t\u0004\u0002\u0002FV\u0005\u0004\u0003\fGH\f\n\u0002\u0002HI\t\u0005",
    "\u0002\u0002IV\u0005\u0004\u0003\u000bJK\f\t\u0002\u0002KL\t\u0006\u0002",
    "\u0002LV\u0005\u0004\u0003\nMN\f\b\u0002\u0002NO\u0007 \u0002\u0002",
    "OV\u0005\u0004\u0003\tPQ\f\u0007\u0002\u0002QR\u0007B\u0002\u0002RV",
    "\u0005\u0004\u0003\bST\f\u000e\u0002\u0002TV\u0005\u0006\u0004\u0002",
    "UA\u0003\u0002\u0002\u0002UD\u0003\u0002\u0002\u0002UG\u0003\u0002\u0002",
    "\u0002UJ\u0003\u0002\u0002\u0002UM\u0003\u0002\u0002\u0002UP\u0003\u0002",
    "\u0002\u0002US\u0003\u0002\u0002\u0002VY\u0003\u0002\u0002\u0002WU\u0003",
    "\u0002\u0002\u0002WX\u0003\u0002\u0002\u0002X\u0005\u0003\u0002\u0002",
    "\u0002YW\u0003\u0002\u0002\u0002Z[\t\u0007\u0002\u0002[\u0007\u0003",
    "\u0002\u0002\u0002\\]\u0005\f\u0007\u0002]\t\u0003\u0002\u0002\u0002",
    "^_\t\b\u0002\u0002_\u000b\u0003\u0002\u0002\u0002`a\t\t\u0002\u0002",
    "a\r\u0003\u0002\u0002\u0002\b,8;?UW"].join("");


const atn = new antlr4.atn.ATNDeserializer().deserialize(serializedATN);

const decisionsToDFA = atn.decisionToState.map( (ds, index) => new antlr4.dfa.DFA(ds, index) );

const sharedContextCache = new antlr4.PredictionContextCache();

export default class BaserowFormula extends antlr4.Parser {

    static grammarFileName = "BaserowFormula.g4";
    static literalNames = [ null, null, null, null, null, null, null, null, 
                            null, "','", "':'", "'::'", "'$'", "'$$'", "'*'", 
                            "'('", "')'", "'['", "']'", null, null, null, 
                            null, null, "'.'", null, null, null, null, "'&'", 
                            "'&&'", "'&<'", "'@@'", "'@>'", "'@'", "'!'", 
                            "'!!'", "'!='", "'^'", "'='", "'=>'", "'>'", 
                            "'>='", "'>>'", "'#'", "'#='", "'#>'", "'#>>'", 
                            "'##'", "'->'", "'->>'", "'-|-'", "'<'", "'<='", 
                            "'<@'", "'<^'", "'<>'", "'<->'", "'<<'", "'<<='", 
                            "'<?>'", "'-'", "'%'", "'|'", "'||'", "'||/'", 
                            "'|/'", "'+'", "'?'", "'?&'", "'?#'", "'?-'", 
                            "'?|'", "'/'", "'~'", "'~='", "'~>=~'", "'~>~'", 
                            "'~<=~'", "'~<~'", "'~*'", "'~~'", "';'" ];
    static symbolicNames = [ null, "BLOCK_COMMENT", "LINE_COMMENT", "WHITESPACE", 
                             "TRUE", "FALSE", "FIELD", "FIELDBYID", "LOOKUP", 
                             "COMMA", "COLON", "COLON_COLON", "DOLLAR", 
                             "DOLLAR_DOLLAR", "STAR", "OPEN_PAREN", "CLOSE_PAREN", 
                             "OPEN_BRACKET", "CLOSE_BRACKET", "BIT_STRING", 
                             "REGEX_STRING", "NUMERIC_LITERAL", "INTEGER_LITERAL", 
                             "HEX_INTEGER_LITERAL", "DOT", "SINGLEQ_STRING_LITERAL", 
                             "DOUBLEQ_STRING_LITERAL", "IDENTIFIER", "IDENTIFIER_UNICODE", 
                             "AMP", "AMP_AMP", "AMP_LT", "AT_AT", "AT_GT", 
                             "AT_SIGN", "BANG", "BANG_BANG", "BANG_EQUAL", 
                             "CARET", "EQUAL", "EQUAL_GT", "GT", "GTE", 
                             "GT_GT", "HASH", "HASH_EQ", "HASH_GT", "HASH_GT_GT", 
                             "HASH_HASH", "HYPHEN_GT", "HYPHEN_GT_GT", "HYPHEN_PIPE_HYPHEN", 
                             "LT", "LTE", "LT_AT", "LT_CARET", "LT_GT", 
                             "LT_HYPHEN_GT", "LT_LT", "LT_LT_EQ", "LT_QMARK_GT", 
                             "MINUS", "PERCENT", "PIPE", "PIPE_PIPE", "PIPE_PIPE_SLASH", 
                             "PIPE_SLASH", "PLUS", "QMARK", "QMARK_AMP", 
                             "QMARK_HASH", "QMARK_HYPHEN", "QMARK_PIPE", 
                             "SLASH", "TIL", "TIL_EQ", "TIL_GTE_TIL", "TIL_GT_TIL", 
                             "TIL_LTE_TIL", "TIL_LT_TIL", "TIL_STAR", "TIL_TIL", 
                             "SEMI", "ErrorCharacter" ];
    static ruleNames = [ "root", "expr", "ws_or_comment", "func_name", "field_reference", 
                         "identifier" ];

    constructor(input) {
        super(input);
        this._interp = new antlr4.atn.ParserATNSimulator(this, atn, decisionsToDFA, sharedContextCache);
        this.ruleNames = BaserowFormula.ruleNames;
        this.literalNames = BaserowFormula.literalNames;
        this.symbolicNames = BaserowFormula.symbolicNames;
    }

    get atn() {
        return atn;
    }

    sempred(localctx, ruleIndex, predIndex) {
    	switch(ruleIndex) {
    	case 1:
    	    		return this.expr_sempred(localctx, predIndex);
        default:
            throw "No predicate with index:" + ruleIndex;
       }
    }

    expr_sempred(localctx, predIndex) {
    	switch(predIndex) {
    		case 0:
    			return this.precpred(this._ctx, 10);
    		case 1:
    			return this.precpred(this._ctx, 9);
    		case 2:
    			return this.precpred(this._ctx, 8);
    		case 3:
    			return this.precpred(this._ctx, 7);
    		case 4:
    			return this.precpred(this._ctx, 6);
    		case 5:
    			return this.precpred(this._ctx, 5);
    		case 6:
    			return this.precpred(this._ctx, 12);
    		default:
    			throw "No predicate with index:" + predIndex;
    	}
    };




	root() {
	    let localctx = new RootContext(this, this._ctx, this.state);
	    this.enterRule(localctx, 0, BaserowFormula.RULE_root);
	    try {
	        this.enterOuterAlt(localctx, 1);
	        this.state = 12;
	        this.expr(0);
	        this.state = 13;
	        this.match(BaserowFormula.EOF);
	    } catch (re) {
	    	if(re instanceof antlr4.error.RecognitionException) {
		        localctx.exception = re;
		        this._errHandler.reportError(this, re);
		        this._errHandler.recover(this, re);
		    } else {
		    	throw re;
		    }
	    } finally {
	        this.exitRule();
	    }
	    return localctx;
	}


	expr(_p) {
		if(_p===undefined) {
		    _p = 0;
		}
	    const _parentctx = this._ctx;
	    const _parentState = this.state;
	    let localctx = new ExprContext(this, this._ctx, _parentState);
	    let _prevctx = localctx;
	    const _startState = 2;
	    this.enterRecursionRule(localctx, 2, BaserowFormula.RULE_expr, _p);
	    var _la = 0; // Token type
	    try {
	        this.enterOuterAlt(localctx, 1);
	        this.state = 61;
	        this._errHandler.sync(this);
	        switch(this._input.LA(1)) {
	        case BaserowFormula.SINGLEQ_STRING_LITERAL:
	            localctx = new StringLiteralContext(this, localctx);
	            this._ctx = localctx;
	            _prevctx = localctx;

	            this.state = 16;
	            this.match(BaserowFormula.SINGLEQ_STRING_LITERAL);
	            break;
	        case BaserowFormula.DOUBLEQ_STRING_LITERAL:
	            localctx = new StringLiteralContext(this, localctx);
	            this._ctx = localctx;
	            _prevctx = localctx;
	            this.state = 17;
	            this.match(BaserowFormula.DOUBLEQ_STRING_LITERAL);
	            break;
	        case BaserowFormula.INTEGER_LITERAL:
	            localctx = new IntegerLiteralContext(this, localctx);
	            this._ctx = localctx;
	            _prevctx = localctx;
	            this.state = 18;
	            this.match(BaserowFormula.INTEGER_LITERAL);
	            break;
	        case BaserowFormula.NUMERIC_LITERAL:
	            localctx = new DecimalLiteralContext(this, localctx);
	            this._ctx = localctx;
	            _prevctx = localctx;
	            this.state = 19;
	            this.match(BaserowFormula.NUMERIC_LITERAL);
	            break;
	        case BaserowFormula.TRUE:
	        case BaserowFormula.FALSE:
	            localctx = new BooleanLiteralContext(this, localctx);
	            this._ctx = localctx;
	            _prevctx = localctx;
	            this.state = 20;
	            _la = this._input.LA(1);
	            if(!(_la===BaserowFormula.TRUE || _la===BaserowFormula.FALSE)) {
	            this._errHandler.recoverInline(this);
	            }
	            else {
	            	this._errHandler.reportMatch(this);
	                this.consume();
	            }
	            break;
	        case BaserowFormula.BLOCK_COMMENT:
	        case BaserowFormula.LINE_COMMENT:
	        case BaserowFormula.WHITESPACE:
	            localctx = new LeftWhitespaceOrCommentsContext(this, localctx);
	            this._ctx = localctx;
	            _prevctx = localctx;
	            this.state = 21;
	            this.ws_or_comment();
	            this.state = 22;
	            this.expr(13);
	            break;
	        case BaserowFormula.OPEN_PAREN:
	            localctx = new BracketsContext(this, localctx);
	            this._ctx = localctx;
	            _prevctx = localctx;
	            this.state = 24;
	            this.match(BaserowFormula.OPEN_PAREN);
	            this.state = 25;
	            this.expr(0);
	            this.state = 26;
	            this.match(BaserowFormula.CLOSE_PAREN);
	            break;
	        case BaserowFormula.FIELD:
	            localctx = new FieldReferenceContext(this, localctx);
	            this._ctx = localctx;
	            _prevctx = localctx;
	            this.state = 28;
	            this.match(BaserowFormula.FIELD);
	            this.state = 29;
	            this.match(BaserowFormula.OPEN_PAREN);
	            this.state = 30;
	            this.field_reference();
	            this.state = 31;
	            this.match(BaserowFormula.CLOSE_PAREN);
	            break;
	        case BaserowFormula.FIELDBYID:
	            localctx = new FieldByIdReferenceContext(this, localctx);
	            this._ctx = localctx;
	            _prevctx = localctx;
	            this.state = 33;
	            this.match(BaserowFormula.FIELDBYID);
	            this.state = 34;
	            this.match(BaserowFormula.OPEN_PAREN);
	            this.state = 35;
	            this.match(BaserowFormula.INTEGER_LITERAL);
	            this.state = 36;
	            this.match(BaserowFormula.CLOSE_PAREN);
	            break;
	        case BaserowFormula.LOOKUP:
	            localctx = new LookupFieldReferenceContext(this, localctx);
	            this._ctx = localctx;
	            _prevctx = localctx;
	            this.state = 37;
	            this.match(BaserowFormula.LOOKUP);
	            this.state = 38;
	            this.match(BaserowFormula.OPEN_PAREN);
	            this.state = 39;
	            this.field_reference();
	            this.state = 40;
	            this.match(BaserowFormula.COMMA);
	            this.state = 42;
	            this._errHandler.sync(this);
	            _la = this._input.LA(1);
	            if(_la===BaserowFormula.WHITESPACE) {
	                this.state = 41;
	                this.match(BaserowFormula.WHITESPACE);
	            }

	            this.state = 44;
	            this.field_reference();
	            this.state = 45;
	            this.match(BaserowFormula.CLOSE_PAREN);
	            break;
	        case BaserowFormula.IDENTIFIER:
	        case BaserowFormula.IDENTIFIER_UNICODE:
	            localctx = new FunctionCallContext(this, localctx);
	            this._ctx = localctx;
	            _prevctx = localctx;
	            this.state = 47;
	            this.func_name();
	            this.state = 48;
	            this.match(BaserowFormula.OPEN_PAREN);
	            this.state = 57;
	            this._errHandler.sync(this);
	            _la = this._input.LA(1);
	            if((((_la) & ~0x1f) == 0 && ((1 << _la) & ((1 << BaserowFormula.BLOCK_COMMENT) | (1 << BaserowFormula.LINE_COMMENT) | (1 << BaserowFormula.WHITESPACE) | (1 << BaserowFormula.TRUE) | (1 << BaserowFormula.FALSE) | (1 << BaserowFormula.FIELD) | (1 << BaserowFormula.FIELDBYID) | (1 << BaserowFormula.LOOKUP) | (1 << BaserowFormula.OPEN_PAREN) | (1 << BaserowFormula.NUMERIC_LITERAL) | (1 << BaserowFormula.INTEGER_LITERAL) | (1 << BaserowFormula.SINGLEQ_STRING_LITERAL) | (1 << BaserowFormula.DOUBLEQ_STRING_LITERAL) | (1 << BaserowFormula.IDENTIFIER) | (1 << BaserowFormula.IDENTIFIER_UNICODE))) !== 0)) {
	                this.state = 49;
	                this.expr(0);
	                this.state = 54;
	                this._errHandler.sync(this);
	                _la = this._input.LA(1);
	                while(_la===BaserowFormula.COMMA) {
	                    this.state = 50;
	                    this.match(BaserowFormula.COMMA);
	                    this.state = 51;
	                    this.expr(0);
	                    this.state = 56;
	                    this._errHandler.sync(this);
	                    _la = this._input.LA(1);
	                }
	            }

	            this.state = 59;
	            this.match(BaserowFormula.CLOSE_PAREN);
	            break;
	        default:
	            throw new antlr4.error.NoViableAltException(this);
	        }
	        this._ctx.stop = this._input.LT(-1);
	        this.state = 85;
	        this._errHandler.sync(this);
	        let _alt = this._interp.adaptivePredict(this._input,5,this._ctx)
	        while(_alt!=2 && _alt!=antlr4.atn.ATN.INVALID_ALT_NUMBER) {
	            if(_alt===1) {
	                if(this._parseListeners!==null) {
	                    this.triggerExitRuleEvent();
	                }
	                _prevctx = localctx;
	                this.state = 83;
	                this._errHandler.sync(this);
	                var la_ = this._interp.adaptivePredict(this._input,4,this._ctx);
	                switch(la_) {
	                case 1:
	                    localctx = new BinaryOpContext(this, new ExprContext(this, _parentctx, _parentState));
	                    this.pushNewRecursionContext(localctx, _startState, BaserowFormula.RULE_expr);
	                    this.state = 63;
	                    if (!( this.precpred(this._ctx, 10))) {
	                        throw new antlr4.error.FailedPredicateException(this, "this.precpred(this._ctx, 10)");
	                    }
	                    this.state = 64;
	                    localctx.op = this._input.LT(1);
	                    _la = this._input.LA(1);
	                    if(!(_la===BaserowFormula.STAR || _la===BaserowFormula.SLASH)) {
	                        localctx.op = this._errHandler.recoverInline(this);
	                    }
	                    else {
	                    	this._errHandler.reportMatch(this);
	                        this.consume();
	                    }
	                    this.state = 65;
	                    this.expr(11);
	                    break;

	                case 2:
	                    localctx = new BinaryOpContext(this, new ExprContext(this, _parentctx, _parentState));
	                    this.pushNewRecursionContext(localctx, _startState, BaserowFormula.RULE_expr);
	                    this.state = 66;
	                    if (!( this.precpred(this._ctx, 9))) {
	                        throw new antlr4.error.FailedPredicateException(this, "this.precpred(this._ctx, 9)");
	                    }
	                    this.state = 67;
	                    localctx.op = this._input.LT(1);
	                    _la = this._input.LA(1);
	                    if(!(_la===BaserowFormula.MINUS || _la===BaserowFormula.PLUS)) {
	                        localctx.op = this._errHandler.recoverInline(this);
	                    }
	                    else {
	                    	this._errHandler.reportMatch(this);
	                        this.consume();
	                    }
	                    this.state = 68;
	                    this.expr(10);
	                    break;

	                case 3:
	                    localctx = new BinaryOpContext(this, new ExprContext(this, _parentctx, _parentState));
	                    this.pushNewRecursionContext(localctx, _startState, BaserowFormula.RULE_expr);
	                    this.state = 69;
	                    if (!( this.precpred(this._ctx, 8))) {
	                        throw new antlr4.error.FailedPredicateException(this, "this.precpred(this._ctx, 8)");
	                    }
	                    this.state = 70;
	                    localctx.op = this._input.LT(1);
	                    _la = this._input.LA(1);
	                    if(!(((((_la - 41)) & ~0x1f) == 0 && ((1 << (_la - 41)) & ((1 << (BaserowFormula.GT - 41)) | (1 << (BaserowFormula.GTE - 41)) | (1 << (BaserowFormula.LT - 41)) | (1 << (BaserowFormula.LTE - 41)))) !== 0))) {
	                        localctx.op = this._errHandler.recoverInline(this);
	                    }
	                    else {
	                    	this._errHandler.reportMatch(this);
	                        this.consume();
	                    }
	                    this.state = 71;
	                    this.expr(9);
	                    break;

	                case 4:
	                    localctx = new BinaryOpContext(this, new ExprContext(this, _parentctx, _parentState));
	                    this.pushNewRecursionContext(localctx, _startState, BaserowFormula.RULE_expr);
	                    this.state = 72;
	                    if (!( this.precpred(this._ctx, 7))) {
	                        throw new antlr4.error.FailedPredicateException(this, "this.precpred(this._ctx, 7)");
	                    }
	                    this.state = 73;
	                    localctx.op = this._input.LT(1);
	                    _la = this._input.LA(1);
	                    if(!(_la===BaserowFormula.BANG_EQUAL || _la===BaserowFormula.EQUAL)) {
	                        localctx.op = this._errHandler.recoverInline(this);
	                    }
	                    else {
	                    	this._errHandler.reportMatch(this);
	                        this.consume();
	                    }
	                    this.state = 74;
	                    this.expr(8);
	                    break;

	                case 5:
	                    localctx = new BinaryOpContext(this, new ExprContext(this, _parentctx, _parentState));
	                    this.pushNewRecursionContext(localctx, _startState, BaserowFormula.RULE_expr);
	                    this.state = 75;
	                    if (!( this.precpred(this._ctx, 6))) {
	                        throw new antlr4.error.FailedPredicateException(this, "this.precpred(this._ctx, 6)");
	                    }
	                    this.state = 76;
	                    localctx.op = this.match(BaserowFormula.AMP_AMP);
	                    this.state = 77;
	                    this.expr(7);
	                    break;

	                case 6:
	                    localctx = new BinaryOpContext(this, new ExprContext(this, _parentctx, _parentState));
	                    this.pushNewRecursionContext(localctx, _startState, BaserowFormula.RULE_expr);
	                    this.state = 78;
	                    if (!( this.precpred(this._ctx, 5))) {
	                        throw new antlr4.error.FailedPredicateException(this, "this.precpred(this._ctx, 5)");
	                    }
	                    this.state = 79;
	                    localctx.op = this.match(BaserowFormula.PIPE_PIPE);
	                    this.state = 80;
	                    this.expr(6);
	                    break;

	                case 7:
	                    localctx = new RightWhitespaceOrCommentsContext(this, new ExprContext(this, _parentctx, _parentState));
	                    this.pushNewRecursionContext(localctx, _startState, BaserowFormula.RULE_expr);
	                    this.state = 81;
	                    if (!( this.precpred(this._ctx, 12))) {
	                        throw new antlr4.error.FailedPredicateException(this, "this.precpred(this._ctx, 12)");
	                    }
	                    this.state = 82;
	                    this.ws_or_comment();
	                    break;

	                } 
	            }
	            this.state = 87;
	            this._errHandler.sync(this);
	            _alt = this._interp.adaptivePredict(this._input,5,this._ctx);
	        }

	    } catch( error) {
	        if(error instanceof antlr4.error.RecognitionException) {
		        localctx.exception = error;
		        this._errHandler.reportError(this, error);
		        this._errHandler.recover(this, error);
		    } else {
		    	throw error;
		    }
	    } finally {
	        this.unrollRecursionContexts(_parentctx)
	    }
	    return localctx;
	}



	ws_or_comment() {
	    let localctx = new Ws_or_commentContext(this, this._ctx, this.state);
	    this.enterRule(localctx, 4, BaserowFormula.RULE_ws_or_comment);
	    var _la = 0; // Token type
	    try {
	        this.enterOuterAlt(localctx, 1);
	        this.state = 88;
	        _la = this._input.LA(1);
	        if(!((((_la) & ~0x1f) == 0 && ((1 << _la) & ((1 << BaserowFormula.BLOCK_COMMENT) | (1 << BaserowFormula.LINE_COMMENT) | (1 << BaserowFormula.WHITESPACE))) !== 0))) {
	        this._errHandler.recoverInline(this);
	        }
	        else {
	        	this._errHandler.reportMatch(this);
	            this.consume();
	        }
	    } catch (re) {
	    	if(re instanceof antlr4.error.RecognitionException) {
		        localctx.exception = re;
		        this._errHandler.reportError(this, re);
		        this._errHandler.recover(this, re);
		    } else {
		    	throw re;
		    }
	    } finally {
	        this.exitRule();
	    }
	    return localctx;
	}



	func_name() {
	    let localctx = new Func_nameContext(this, this._ctx, this.state);
	    this.enterRule(localctx, 6, BaserowFormula.RULE_func_name);
	    try {
	        this.enterOuterAlt(localctx, 1);
	        this.state = 90;
	        this.identifier();
	    } catch (re) {
	    	if(re instanceof antlr4.error.RecognitionException) {
		        localctx.exception = re;
		        this._errHandler.reportError(this, re);
		        this._errHandler.recover(this, re);
		    } else {
		    	throw re;
		    }
	    } finally {
	        this.exitRule();
	    }
	    return localctx;
	}



	field_reference() {
	    let localctx = new Field_referenceContext(this, this._ctx, this.state);
	    this.enterRule(localctx, 8, BaserowFormula.RULE_field_reference);
	    var _la = 0; // Token type
	    try {
	        this.enterOuterAlt(localctx, 1);
	        this.state = 92;
	        _la = this._input.LA(1);
	        if(!(_la===BaserowFormula.SINGLEQ_STRING_LITERAL || _la===BaserowFormula.DOUBLEQ_STRING_LITERAL)) {
	        this._errHandler.recoverInline(this);
	        }
	        else {
	        	this._errHandler.reportMatch(this);
	            this.consume();
	        }
	    } catch (re) {
	    	if(re instanceof antlr4.error.RecognitionException) {
		        localctx.exception = re;
		        this._errHandler.reportError(this, re);
		        this._errHandler.recover(this, re);
		    } else {
		    	throw re;
		    }
	    } finally {
	        this.exitRule();
	    }
	    return localctx;
	}



	identifier() {
	    let localctx = new IdentifierContext(this, this._ctx, this.state);
	    this.enterRule(localctx, 10, BaserowFormula.RULE_identifier);
	    var _la = 0; // Token type
	    try {
	        this.enterOuterAlt(localctx, 1);
	        this.state = 94;
	        _la = this._input.LA(1);
	        if(!(_la===BaserowFormula.IDENTIFIER || _la===BaserowFormula.IDENTIFIER_UNICODE)) {
	        this._errHandler.recoverInline(this);
	        }
	        else {
	        	this._errHandler.reportMatch(this);
	            this.consume();
	        }
	    } catch (re) {
	    	if(re instanceof antlr4.error.RecognitionException) {
		        localctx.exception = re;
		        this._errHandler.reportError(this, re);
		        this._errHandler.recover(this, re);
		    } else {
		    	throw re;
		    }
	    } finally {
	        this.exitRule();
	    }
	    return localctx;
	}


}

BaserowFormula.EOF = antlr4.Token.EOF;
BaserowFormula.BLOCK_COMMENT = 1;
BaserowFormula.LINE_COMMENT = 2;
BaserowFormula.WHITESPACE = 3;
BaserowFormula.TRUE = 4;
BaserowFormula.FALSE = 5;
BaserowFormula.FIELD = 6;
BaserowFormula.FIELDBYID = 7;
BaserowFormula.LOOKUP = 8;
BaserowFormula.COMMA = 9;
BaserowFormula.COLON = 10;
BaserowFormula.COLON_COLON = 11;
BaserowFormula.DOLLAR = 12;
BaserowFormula.DOLLAR_DOLLAR = 13;
BaserowFormula.STAR = 14;
BaserowFormula.OPEN_PAREN = 15;
BaserowFormula.CLOSE_PAREN = 16;
BaserowFormula.OPEN_BRACKET = 17;
BaserowFormula.CLOSE_BRACKET = 18;
BaserowFormula.BIT_STRING = 19;
BaserowFormula.REGEX_STRING = 20;
BaserowFormula.NUMERIC_LITERAL = 21;
BaserowFormula.INTEGER_LITERAL = 22;
BaserowFormula.HEX_INTEGER_LITERAL = 23;
BaserowFormula.DOT = 24;
BaserowFormula.SINGLEQ_STRING_LITERAL = 25;
BaserowFormula.DOUBLEQ_STRING_LITERAL = 26;
BaserowFormula.IDENTIFIER = 27;
BaserowFormula.IDENTIFIER_UNICODE = 28;
BaserowFormula.AMP = 29;
BaserowFormula.AMP_AMP = 30;
BaserowFormula.AMP_LT = 31;
BaserowFormula.AT_AT = 32;
BaserowFormula.AT_GT = 33;
BaserowFormula.AT_SIGN = 34;
BaserowFormula.BANG = 35;
BaserowFormula.BANG_BANG = 36;
BaserowFormula.BANG_EQUAL = 37;
BaserowFormula.CARET = 38;
BaserowFormula.EQUAL = 39;
BaserowFormula.EQUAL_GT = 40;
BaserowFormula.GT = 41;
BaserowFormula.GTE = 42;
BaserowFormula.GT_GT = 43;
BaserowFormula.HASH = 44;
BaserowFormula.HASH_EQ = 45;
BaserowFormula.HASH_GT = 46;
BaserowFormula.HASH_GT_GT = 47;
BaserowFormula.HASH_HASH = 48;
BaserowFormula.HYPHEN_GT = 49;
BaserowFormula.HYPHEN_GT_GT = 50;
BaserowFormula.HYPHEN_PIPE_HYPHEN = 51;
BaserowFormula.LT = 52;
BaserowFormula.LTE = 53;
BaserowFormula.LT_AT = 54;
BaserowFormula.LT_CARET = 55;
BaserowFormula.LT_GT = 56;
BaserowFormula.LT_HYPHEN_GT = 57;
BaserowFormula.LT_LT = 58;
BaserowFormula.LT_LT_EQ = 59;
BaserowFormula.LT_QMARK_GT = 60;
BaserowFormula.MINUS = 61;
BaserowFormula.PERCENT = 62;
BaserowFormula.PIPE = 63;
BaserowFormula.PIPE_PIPE = 64;
BaserowFormula.PIPE_PIPE_SLASH = 65;
BaserowFormula.PIPE_SLASH = 66;
BaserowFormula.PLUS = 67;
BaserowFormula.QMARK = 68;
BaserowFormula.QMARK_AMP = 69;
BaserowFormula.QMARK_HASH = 70;
BaserowFormula.QMARK_HYPHEN = 71;
BaserowFormula.QMARK_PIPE = 72;
BaserowFormula.SLASH = 73;
BaserowFormula.TIL = 74;
BaserowFormula.TIL_EQ = 75;
BaserowFormula.TIL_GTE_TIL = 76;
BaserowFormula.TIL_GT_TIL = 77;
BaserowFormula.TIL_LTE_TIL = 78;
BaserowFormula.TIL_LT_TIL = 79;
BaserowFormula.TIL_STAR = 80;
BaserowFormula.TIL_TIL = 81;
BaserowFormula.SEMI = 82;
BaserowFormula.ErrorCharacter = 83;

BaserowFormula.RULE_root = 0;
BaserowFormula.RULE_expr = 1;
BaserowFormula.RULE_ws_or_comment = 2;
BaserowFormula.RULE_func_name = 3;
BaserowFormula.RULE_field_reference = 4;
BaserowFormula.RULE_identifier = 5;

class RootContext extends antlr4.ParserRuleContext {

    constructor(parser, parent, invokingState) {
        if(parent===undefined) {
            parent = null;
        }
        if(invokingState===undefined || invokingState===null) {
            invokingState = -1;
        }
        super(parent, invokingState);
        this.parser = parser;
        this.ruleIndex = BaserowFormula.RULE_root;
    }

	expr() {
	    return this.getTypedRuleContext(ExprContext,0);
	};

	EOF() {
	    return this.getToken(BaserowFormula.EOF, 0);
	};

	enterRule(listener) {
	    if(listener instanceof BaserowFormulaListener ) {
	        listener.enterRoot(this);
		}
	}

	exitRule(listener) {
	    if(listener instanceof BaserowFormulaListener ) {
	        listener.exitRoot(this);
		}
	}

	accept(visitor) {
	    if ( visitor instanceof BaserowFormulaVisitor ) {
	        return visitor.visitRoot(this);
	    } else {
	        return visitor.visitChildren(this);
	    }
	}


}



class ExprContext extends antlr4.ParserRuleContext {

    constructor(parser, parent, invokingState) {
        if(parent===undefined) {
            parent = null;
        }
        if(invokingState===undefined || invokingState===null) {
            invokingState = -1;
        }
        super(parent, invokingState);
        this.parser = parser;
        this.ruleIndex = BaserowFormula.RULE_expr;
    }


	 
		copyFrom(ctx) {
			super.copyFrom(ctx);
		}

}


class FieldReferenceContext extends ExprContext {

    constructor(parser, ctx) {
        super(parser);
        super.copyFrom(ctx);
    }

	FIELD() {
	    return this.getToken(BaserowFormula.FIELD, 0);
	};

	OPEN_PAREN() {
	    return this.getToken(BaserowFormula.OPEN_PAREN, 0);
	};

	field_reference() {
	    return this.getTypedRuleContext(Field_referenceContext,0);
	};

	CLOSE_PAREN() {
	    return this.getToken(BaserowFormula.CLOSE_PAREN, 0);
	};

	enterRule(listener) {
	    if(listener instanceof BaserowFormulaListener ) {
	        listener.enterFieldReference(this);
		}
	}

	exitRule(listener) {
	    if(listener instanceof BaserowFormulaListener ) {
	        listener.exitFieldReference(this);
		}
	}

	accept(visitor) {
	    if ( visitor instanceof BaserowFormulaVisitor ) {
	        return visitor.visitFieldReference(this);
	    } else {
	        return visitor.visitChildren(this);
	    }
	}


}

BaserowFormula.FieldReferenceContext = FieldReferenceContext;

class StringLiteralContext extends ExprContext {

    constructor(parser, ctx) {
        super(parser);
        super.copyFrom(ctx);
    }

	SINGLEQ_STRING_LITERAL() {
	    return this.getToken(BaserowFormula.SINGLEQ_STRING_LITERAL, 0);
	};

	DOUBLEQ_STRING_LITERAL() {
	    return this.getToken(BaserowFormula.DOUBLEQ_STRING_LITERAL, 0);
	};

	enterRule(listener) {
	    if(listener instanceof BaserowFormulaListener ) {
	        listener.enterStringLiteral(this);
		}
	}

	exitRule(listener) {
	    if(listener instanceof BaserowFormulaListener ) {
	        listener.exitStringLiteral(this);
		}
	}

	accept(visitor) {
	    if ( visitor instanceof BaserowFormulaVisitor ) {
	        return visitor.visitStringLiteral(this);
	    } else {
	        return visitor.visitChildren(this);
	    }
	}


}

BaserowFormula.StringLiteralContext = StringLiteralContext;

class BracketsContext extends ExprContext {

    constructor(parser, ctx) {
        super(parser);
        super.copyFrom(ctx);
    }

	OPEN_PAREN() {
	    return this.getToken(BaserowFormula.OPEN_PAREN, 0);
	};

	expr() {
	    return this.getTypedRuleContext(ExprContext,0);
	};

	CLOSE_PAREN() {
	    return this.getToken(BaserowFormula.CLOSE_PAREN, 0);
	};

	enterRule(listener) {
	    if(listener instanceof BaserowFormulaListener ) {
	        listener.enterBrackets(this);
		}
	}

	exitRule(listener) {
	    if(listener instanceof BaserowFormulaListener ) {
	        listener.exitBrackets(this);
		}
	}

	accept(visitor) {
	    if ( visitor instanceof BaserowFormulaVisitor ) {
	        return visitor.visitBrackets(this);
	    } else {
	        return visitor.visitChildren(this);
	    }
	}


}

BaserowFormula.BracketsContext = BracketsContext;

class BooleanLiteralContext extends ExprContext {

    constructor(parser, ctx) {
        super(parser);
        super.copyFrom(ctx);
    }

	TRUE() {
	    return this.getToken(BaserowFormula.TRUE, 0);
	};

	FALSE() {
	    return this.getToken(BaserowFormula.FALSE, 0);
	};

	enterRule(listener) {
	    if(listener instanceof BaserowFormulaListener ) {
	        listener.enterBooleanLiteral(this);
		}
	}

	exitRule(listener) {
	    if(listener instanceof BaserowFormulaListener ) {
	        listener.exitBooleanLiteral(this);
		}
	}

	accept(visitor) {
	    if ( visitor instanceof BaserowFormulaVisitor ) {
	        return visitor.visitBooleanLiteral(this);
	    } else {
	        return visitor.visitChildren(this);
	    }
	}


}

BaserowFormula.BooleanLiteralContext = BooleanLiteralContext;

class RightWhitespaceOrCommentsContext extends ExprContext {

    constructor(parser, ctx) {
        super(parser);
        super.copyFrom(ctx);
    }

	expr() {
	    return this.getTypedRuleContext(ExprContext,0);
	};

	ws_or_comment() {
	    return this.getTypedRuleContext(Ws_or_commentContext,0);
	};

	enterRule(listener) {
	    if(listener instanceof BaserowFormulaListener ) {
	        listener.enterRightWhitespaceOrComments(this);
		}
	}

	exitRule(listener) {
	    if(listener instanceof BaserowFormulaListener ) {
	        listener.exitRightWhitespaceOrComments(this);
		}
	}

	accept(visitor) {
	    if ( visitor instanceof BaserowFormulaVisitor ) {
	        return visitor.visitRightWhitespaceOrComments(this);
	    } else {
	        return visitor.visitChildren(this);
	    }
	}


}

BaserowFormula.RightWhitespaceOrCommentsContext = RightWhitespaceOrCommentsContext;

class DecimalLiteralContext extends ExprContext {

    constructor(parser, ctx) {
        super(parser);
        super.copyFrom(ctx);
    }

	NUMERIC_LITERAL() {
	    return this.getToken(BaserowFormula.NUMERIC_LITERAL, 0);
	};

	enterRule(listener) {
	    if(listener instanceof BaserowFormulaListener ) {
	        listener.enterDecimalLiteral(this);
		}
	}

	exitRule(listener) {
	    if(listener instanceof BaserowFormulaListener ) {
	        listener.exitDecimalLiteral(this);
		}
	}

	accept(visitor) {
	    if ( visitor instanceof BaserowFormulaVisitor ) {
	        return visitor.visitDecimalLiteral(this);
	    } else {
	        return visitor.visitChildren(this);
	    }
	}


}

BaserowFormula.DecimalLiteralContext = DecimalLiteralContext;

class LeftWhitespaceOrCommentsContext extends ExprContext {

    constructor(parser, ctx) {
        super(parser);
        super.copyFrom(ctx);
    }

	ws_or_comment() {
	    return this.getTypedRuleContext(Ws_or_commentContext,0);
	};

	expr() {
	    return this.getTypedRuleContext(ExprContext,0);
	};

	enterRule(listener) {
	    if(listener instanceof BaserowFormulaListener ) {
	        listener.enterLeftWhitespaceOrComments(this);
		}
	}

	exitRule(listener) {
	    if(listener instanceof BaserowFormulaListener ) {
	        listener.exitLeftWhitespaceOrComments(this);
		}
	}

	accept(visitor) {
	    if ( visitor instanceof BaserowFormulaVisitor ) {
	        return visitor.visitLeftWhitespaceOrComments(this);
	    } else {
	        return visitor.visitChildren(this);
	    }
	}


}

BaserowFormula.LeftWhitespaceOrCommentsContext = LeftWhitespaceOrCommentsContext;

class FunctionCallContext extends ExprContext {

    constructor(parser, ctx) {
        super(parser);
        super.copyFrom(ctx);
    }

	func_name() {
	    return this.getTypedRuleContext(Func_nameContext,0);
	};

	OPEN_PAREN() {
	    return this.getToken(BaserowFormula.OPEN_PAREN, 0);
	};

	CLOSE_PAREN() {
	    return this.getToken(BaserowFormula.CLOSE_PAREN, 0);
	};

	expr = function(i) {
	    if(i===undefined) {
	        i = null;
	    }
	    if(i===null) {
	        return this.getTypedRuleContexts(ExprContext);
	    } else {
	        return this.getTypedRuleContext(ExprContext,i);
	    }
	};

	COMMA = function(i) {
		if(i===undefined) {
			i = null;
		}
	    if(i===null) {
	        return this.getTokens(BaserowFormula.COMMA);
	    } else {
	        return this.getToken(BaserowFormula.COMMA, i);
	    }
	};


	enterRule(listener) {
	    if(listener instanceof BaserowFormulaListener ) {
	        listener.enterFunctionCall(this);
		}
	}

	exitRule(listener) {
	    if(listener instanceof BaserowFormulaListener ) {
	        listener.exitFunctionCall(this);
		}
	}

	accept(visitor) {
	    if ( visitor instanceof BaserowFormulaVisitor ) {
	        return visitor.visitFunctionCall(this);
	    } else {
	        return visitor.visitChildren(this);
	    }
	}


}

BaserowFormula.FunctionCallContext = FunctionCallContext;

class FieldByIdReferenceContext extends ExprContext {

    constructor(parser, ctx) {
        super(parser);
        super.copyFrom(ctx);
    }

	FIELDBYID() {
	    return this.getToken(BaserowFormula.FIELDBYID, 0);
	};

	OPEN_PAREN() {
	    return this.getToken(BaserowFormula.OPEN_PAREN, 0);
	};

	INTEGER_LITERAL() {
	    return this.getToken(BaserowFormula.INTEGER_LITERAL, 0);
	};

	CLOSE_PAREN() {
	    return this.getToken(BaserowFormula.CLOSE_PAREN, 0);
	};

	enterRule(listener) {
	    if(listener instanceof BaserowFormulaListener ) {
	        listener.enterFieldByIdReference(this);
		}
	}

	exitRule(listener) {
	    if(listener instanceof BaserowFormulaListener ) {
	        listener.exitFieldByIdReference(this);
		}
	}

	accept(visitor) {
	    if ( visitor instanceof BaserowFormulaVisitor ) {
	        return visitor.visitFieldByIdReference(this);
	    } else {
	        return visitor.visitChildren(this);
	    }
	}


}

BaserowFormula.FieldByIdReferenceContext = FieldByIdReferenceContext;

class LookupFieldReferenceContext extends ExprContext {

    constructor(parser, ctx) {
        super(parser);
        super.copyFrom(ctx);
    }

	LOOKUP() {
	    return this.getToken(BaserowFormula.LOOKUP, 0);
	};

	OPEN_PAREN() {
	    return this.getToken(BaserowFormula.OPEN_PAREN, 0);
	};

	field_reference = function(i) {
	    if(i===undefined) {
	        i = null;
	    }
	    if(i===null) {
	        return this.getTypedRuleContexts(Field_referenceContext);
	    } else {
	        return this.getTypedRuleContext(Field_referenceContext,i);
	    }
	};

	COMMA() {
	    return this.getToken(BaserowFormula.COMMA, 0);
	};

	CLOSE_PAREN() {
	    return this.getToken(BaserowFormula.CLOSE_PAREN, 0);
	};

	WHITESPACE() {
	    return this.getToken(BaserowFormula.WHITESPACE, 0);
	};

	enterRule(listener) {
	    if(listener instanceof BaserowFormulaListener ) {
	        listener.enterLookupFieldReference(this);
		}
	}

	exitRule(listener) {
	    if(listener instanceof BaserowFormulaListener ) {
	        listener.exitLookupFieldReference(this);
		}
	}

	accept(visitor) {
	    if ( visitor instanceof BaserowFormulaVisitor ) {
	        return visitor.visitLookupFieldReference(this);
	    } else {
	        return visitor.visitChildren(this);
	    }
	}


}

BaserowFormula.LookupFieldReferenceContext = LookupFieldReferenceContext;

class IntegerLiteralContext extends ExprContext {

    constructor(parser, ctx) {
        super(parser);
        super.copyFrom(ctx);
    }

	INTEGER_LITERAL() {
	    return this.getToken(BaserowFormula.INTEGER_LITERAL, 0);
	};

	enterRule(listener) {
	    if(listener instanceof BaserowFormulaListener ) {
	        listener.enterIntegerLiteral(this);
		}
	}

	exitRule(listener) {
	    if(listener instanceof BaserowFormulaListener ) {
	        listener.exitIntegerLiteral(this);
		}
	}

	accept(visitor) {
	    if ( visitor instanceof BaserowFormulaVisitor ) {
	        return visitor.visitIntegerLiteral(this);
	    } else {
	        return visitor.visitChildren(this);
	    }
	}


}

BaserowFormula.IntegerLiteralContext = IntegerLiteralContext;

class BinaryOpContext extends ExprContext {

    constructor(parser, ctx) {
        super(parser);
        this.op = null; // Token;
        super.copyFrom(ctx);
    }

	expr = function(i) {
	    if(i===undefined) {
	        i = null;
	    }
	    if(i===null) {
	        return this.getTypedRuleContexts(ExprContext);
	    } else {
	        return this.getTypedRuleContext(ExprContext,i);
	    }
	};

	SLASH() {
	    return this.getToken(BaserowFormula.SLASH, 0);
	};

	STAR() {
	    return this.getToken(BaserowFormula.STAR, 0);
	};

	PLUS() {
	    return this.getToken(BaserowFormula.PLUS, 0);
	};

	MINUS() {
	    return this.getToken(BaserowFormula.MINUS, 0);
	};

	GT() {
	    return this.getToken(BaserowFormula.GT, 0);
	};

	LT() {
	    return this.getToken(BaserowFormula.LT, 0);
	};

	GTE() {
	    return this.getToken(BaserowFormula.GTE, 0);
	};

	LTE() {
	    return this.getToken(BaserowFormula.LTE, 0);
	};

	EQUAL() {
	    return this.getToken(BaserowFormula.EQUAL, 0);
	};

	BANG_EQUAL() {
	    return this.getToken(BaserowFormula.BANG_EQUAL, 0);
	};

	AMP_AMP() {
	    return this.getToken(BaserowFormula.AMP_AMP, 0);
	};

	PIPE_PIPE() {
	    return this.getToken(BaserowFormula.PIPE_PIPE, 0);
	};

	enterRule(listener) {
	    if(listener instanceof BaserowFormulaListener ) {
	        listener.enterBinaryOp(this);
		}
	}

	exitRule(listener) {
	    if(listener instanceof BaserowFormulaListener ) {
	        listener.exitBinaryOp(this);
		}
	}

	accept(visitor) {
	    if ( visitor instanceof BaserowFormulaVisitor ) {
	        return visitor.visitBinaryOp(this);
	    } else {
	        return visitor.visitChildren(this);
	    }
	}


}

BaserowFormula.BinaryOpContext = BinaryOpContext;

class Ws_or_commentContext extends antlr4.ParserRuleContext {

    constructor(parser, parent, invokingState) {
        if(parent===undefined) {
            parent = null;
        }
        if(invokingState===undefined || invokingState===null) {
            invokingState = -1;
        }
        super(parent, invokingState);
        this.parser = parser;
        this.ruleIndex = BaserowFormula.RULE_ws_or_comment;
    }

	BLOCK_COMMENT() {
	    return this.getToken(BaserowFormula.BLOCK_COMMENT, 0);
	};

	LINE_COMMENT() {
	    return this.getToken(BaserowFormula.LINE_COMMENT, 0);
	};

	WHITESPACE() {
	    return this.getToken(BaserowFormula.WHITESPACE, 0);
	};

	enterRule(listener) {
	    if(listener instanceof BaserowFormulaListener ) {
	        listener.enterWs_or_comment(this);
		}
	}

	exitRule(listener) {
	    if(listener instanceof BaserowFormulaListener ) {
	        listener.exitWs_or_comment(this);
		}
	}

	accept(visitor) {
	    if ( visitor instanceof BaserowFormulaVisitor ) {
	        return visitor.visitWs_or_comment(this);
	    } else {
	        return visitor.visitChildren(this);
	    }
	}


}



class Func_nameContext extends antlr4.ParserRuleContext {

    constructor(parser, parent, invokingState) {
        if(parent===undefined) {
            parent = null;
        }
        if(invokingState===undefined || invokingState===null) {
            invokingState = -1;
        }
        super(parent, invokingState);
        this.parser = parser;
        this.ruleIndex = BaserowFormula.RULE_func_name;
    }

	identifier() {
	    return this.getTypedRuleContext(IdentifierContext,0);
	};

	enterRule(listener) {
	    if(listener instanceof BaserowFormulaListener ) {
	        listener.enterFunc_name(this);
		}
	}

	exitRule(listener) {
	    if(listener instanceof BaserowFormulaListener ) {
	        listener.exitFunc_name(this);
		}
	}

	accept(visitor) {
	    if ( visitor instanceof BaserowFormulaVisitor ) {
	        return visitor.visitFunc_name(this);
	    } else {
	        return visitor.visitChildren(this);
	    }
	}


}



class Field_referenceContext extends antlr4.ParserRuleContext {

    constructor(parser, parent, invokingState) {
        if(parent===undefined) {
            parent = null;
        }
        if(invokingState===undefined || invokingState===null) {
            invokingState = -1;
        }
        super(parent, invokingState);
        this.parser = parser;
        this.ruleIndex = BaserowFormula.RULE_field_reference;
    }

	SINGLEQ_STRING_LITERAL() {
	    return this.getToken(BaserowFormula.SINGLEQ_STRING_LITERAL, 0);
	};

	DOUBLEQ_STRING_LITERAL() {
	    return this.getToken(BaserowFormula.DOUBLEQ_STRING_LITERAL, 0);
	};

	enterRule(listener) {
	    if(listener instanceof BaserowFormulaListener ) {
	        listener.enterField_reference(this);
		}
	}

	exitRule(listener) {
	    if(listener instanceof BaserowFormulaListener ) {
	        listener.exitField_reference(this);
		}
	}

	accept(visitor) {
	    if ( visitor instanceof BaserowFormulaVisitor ) {
	        return visitor.visitField_reference(this);
	    } else {
	        return visitor.visitChildren(this);
	    }
	}


}



class IdentifierContext extends antlr4.ParserRuleContext {

    constructor(parser, parent, invokingState) {
        if(parent===undefined) {
            parent = null;
        }
        if(invokingState===undefined || invokingState===null) {
            invokingState = -1;
        }
        super(parent, invokingState);
        this.parser = parser;
        this.ruleIndex = BaserowFormula.RULE_identifier;
    }

	IDENTIFIER() {
	    return this.getToken(BaserowFormula.IDENTIFIER, 0);
	};

	IDENTIFIER_UNICODE() {
	    return this.getToken(BaserowFormula.IDENTIFIER_UNICODE, 0);
	};

	enterRule(listener) {
	    if(listener instanceof BaserowFormulaListener ) {
	        listener.enterIdentifier(this);
		}
	}

	exitRule(listener) {
	    if(listener instanceof BaserowFormulaListener ) {
	        listener.exitIdentifier(this);
		}
	}

	accept(visitor) {
	    if ( visitor instanceof BaserowFormulaVisitor ) {
	        return visitor.visitIdentifier(this);
	    } else {
	        return visitor.visitChildren(this);
	    }
	}


}




BaserowFormula.RootContext = RootContext; 
BaserowFormula.ExprContext = ExprContext; 
BaserowFormula.Ws_or_commentContext = Ws_or_commentContext; 
BaserowFormula.Func_nameContext = Func_nameContext; 
BaserowFormula.Field_referenceContext = Field_referenceContext; 
BaserowFormula.IdentifierContext = IdentifierContext; 
