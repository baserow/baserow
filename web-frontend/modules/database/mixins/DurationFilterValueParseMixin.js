import _ from 'lodash'
export default {
  /**
   * Helper to parse duration specific filterValue. A filterValue comes a string
   * containing a number of seconds, thus duration field needs to parse it to a correct
   * number of seconds, but a string with a number may mean a different thing. It can
   * be a number of seconds, a number of minutes or a number of hours depending
   * on field.duration_format value.
   *
   * This method ensures that if a field is of duration type (a duration field or a
   * duration formula field), and filterValue is a number, it will receive field
   * context with a correct duration format to ensure that filterValue will be
   * understood as a number of seconds.
   *
   * If filterValue is not a number, field's duration_format will be used to parse
   * duration.
   *
   * @param field
   * @param fieldType
   * @param filterValue
   * @returns {number}
   * @private
   */
  _parseDurationValue(field, fieldType, filterValue) {
    if (field.type === 'duration' || field.formula_type === 'duration') {
      let durationFormat = field.duration_format
      if (_.isNumber(filterValue)) {
        durationFormat = 'h:mm:ss'
      }

      return fieldType.parseInputValue(
        { ...field, duration_format: durationFormat },
        filterValue
      )
    } else {
      return fieldType.parseInputValue(field, filterValue)
    }
  },
}
