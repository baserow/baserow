import { Registerable } from '@baserow/modules/core/registry'

const TEXT_FORMULA_TYPES = ['text', 'char', 'url']

/**
 * Makes a field type compatible with semantic search. The type must match the
 * type of the field type.
 */
export class SemanticSearchFieldType extends Registerable {
  isCompatible(field) {
    return true
  }
}

export class TextSemanticSearchFieldType extends SemanticSearchFieldType {
  static getType() {
    return 'text'
  }
}

export class LongTextSemanticSearchFieldType extends SemanticSearchFieldType {
  static getType() {
    return 'long_text'
  }
}

export class URLSemanticSearchFieldType extends SemanticSearchFieldType {
  static getType() {
    return 'url'
  }
}

export class EmailSemanticSearchFieldType extends SemanticSearchFieldType {
  static getType() {
    return 'email'
  }
}

export class PhoneNumberSemanticSearchFieldType extends SemanticSearchFieldType {
  static getType() {
    return 'phone_number'
  }
}

export class FormulaSemanticSearchFieldType extends SemanticSearchFieldType {
  static getType() {
    return 'formula'
  }

  isCompatible(field) {
    // The type of a formula is only known after it has been saved, so the backend
    // decides for new formulas.
    if (!field.formula_type) {
      return true
    }
    const type =
      field.formula_type === 'array'
        ? field.array_formula_type
        : field.formula_type
    return TEXT_FORMULA_TYPES.includes(type)
  }
}

export class LookupSemanticSearchFieldType extends FormulaSemanticSearchFieldType {
  static getType() {
    return 'lookup'
  }
}

export class RollupSemanticSearchFieldType extends FormulaSemanticSearchFieldType {
  static getType() {
    return 'rollup'
  }
}

export class AISemanticSearchFieldType extends SemanticSearchFieldType {
  static getType() {
    return 'ai'
  }

  isCompatible(field) {
    return (field.ai_output_type || 'text') === 'text'
  }
}
