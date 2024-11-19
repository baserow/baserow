export default {
  /**
   * Helper to parse duration specific filterValue. A filterValue comes a string
   * containing a number of seconds, thus duration field needs to parse it to a correct
   * number of seconds, but a string with a number may mean a different thing. It can
   * be a number of seconds, a number of minutes or a number of hours depending
   * on field.duration_format value.
   *
   * This method ensures that if a field is of duration type (a duration field or a
   * duration formula field), it will receive field context with a correct duration
   * format to ensure that filterValue will be understood as a number of seconds.
   *
   * @param field
   * @param fieldType
   * @param filterValue
   * @returns {number}
   * @private
   */
  _parseDurationValue(field, fieldType, filterValue) {
    if (field.type === 'duration' || field.formula_type === 'duration') {
      return fieldType.parseInputValue(
        { ...field, duration_format: 'h:mm:ss' },
        filterValue
      )
    } else {
      return fieldType.parseInputValue(field, filterValue)
    }
  },
}
