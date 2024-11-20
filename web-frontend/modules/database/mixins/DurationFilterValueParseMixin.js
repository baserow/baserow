import _ from 'lodash'
export default {
  /**
   * Helper method to parse duration-specific filterValue. A filterValue comes as a
   * string. In case of duration-related fields, duration value may come in various
   * forms, as those fields support different formatting styles.
   *
   * Duration value may be unit-aware or "naive". Unit-aware values are easier to parse
   * because they already tell which unit should be used, for example `1d 2h 3m 4s`.
   * "Naive" values don't have unit information by themselves. Parsing those values
   * relies on a duration format picked for a given field. "Naive" values are usually
   * numbers or values in `12:34` notation. If duration format picked contains seconds,
   * usually those values are interpreted with a second as a lowest unit. In other
   * cases, a number may be interpreted as a number of minutes or hours.
   *
   * This method ensures that if a field is of duration type (a duration field or a
   * duration formula field), and filterValue is "naive", it will receive field
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
