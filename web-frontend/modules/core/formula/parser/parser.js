import antlr4 from 'antlr4'
import BaserowFormulaLexer from '@baserow/modules/core/formula/parser/generated/BaserowFormulaLexer'
import BaserowFormula from '@baserow/modules/core/formula/parser/generated/BaserowFormula'
import { BaserowFormulaParserError } from '@baserow/modules/core/formula/parser/errors'

/**
 * Attempts to parse an input string into a Baserow Formula. If it fails a
 * BaserowFormulaParserError will be raised.
 *
 * @param formula
 * @return {*} The resulting antlr4 parse tree of the formula
 */
export default function parseBaserowFormula(formula, throwOnError = true) {
  const chars = new antlr4.InputStream(formula)
  const lexer = new BaserowFormulaLexer(chars)
  const tokens = new antlr4.CommonTokenStream(lexer)
  const parser = new BaserowFormula(tokens)
  parser.removeErrorListeners()
  // noinspection JSUnusedLocalSymbols
  parser.addErrorListener({
    syntaxError: (recognizer, offendingSymbol, line, column, msg, err) => {
      if (throwOnError) {
        throw new BaserowFormulaParserError(offendingSymbol, line, column, msg)
      }
    },
  })
  parser.buildParseTrees = true
  return parser.root()
}

export function getTokenStreamForFormula(formula) {
  const chars = new antlr4.InputStream(formula)
  const lexer = new BaserowFormulaLexer(chars)
  const stream = new antlr4.CommonTokenStream(lexer)
  stream.lazyInit()
  stream.fill()
  return stream
}
