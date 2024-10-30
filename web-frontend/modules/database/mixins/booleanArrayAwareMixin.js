export default {
  /**
   * Determines if a field struct describes a boolean array formula field.
   */
  isBooleanArrayField(field) {
    return (
      field.array_formula_type === 'boolean' && field.formula_type === 'array'
    )
  },
}
