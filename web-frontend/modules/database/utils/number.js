import BigNumber from 'bignumber.js'

// We use these constants to map the separators to the values used in the database.
// The same variables are used in the backend.

const THOUSAND_SEPARATORS = {
  SPACE: ' ',
  COMMA: ',',
  PERIOD: '.',
  NONE: '',
}

const DECIMAL_SEPARATORS = {
  COMMA: ',',
  PERIOD: '.',
}

const NUMBER_MAX_DECIMAL_PLACES = 10

const DEFAULT_THOUSAND_SEPARATOR = THOUSAND_SEPARATORS.NONE
const DEFAULT_DECIMAL_SEPARATOR = DECIMAL_SEPARATORS.PERIOD

export const NUMBER_FORMATS = {
  NO_FORMATTING: {
    thousandSeparator: DEFAULT_THOUSAND_SEPARATOR,
    decimalSeparator: DEFAULT_DECIMAL_SEPARATOR,
    description: 'fieldNumberSubForm.noFormatting',
    value: '',
  },
  SPACE_COMMA: {
    thousandSeparator: THOUSAND_SEPARATORS.SPACE,
    decimalSeparator: DECIMAL_SEPARATORS.COMMA,
    description: 'fieldNumberSubForm.spaceComma',
    value: 'SPACE_COMMA',
  },
  SPACE_PERIOD: {
    thousandSeparator: THOUSAND_SEPARATORS.SPACE,
    decimalSeparator: DECIMAL_SEPARATORS.PERIOD,
    description: 'fieldNumberSubForm.spacePeriod',
    value: 'SPACE_PERIOD',
  },
  COMMA_PERIOD: {
    thousandSeparator: THOUSAND_SEPARATORS.COMMA,
    decimalSeparator: DECIMAL_SEPARATORS.PERIOD,
    description: 'fieldNumberSubForm.commaPeriod',
    value: 'COMMA_PERIOD',
  },
  PERIOD_COMMA: {
    thousandSeparator: THOUSAND_SEPARATORS.PERIOD,
    decimalSeparator: DECIMAL_SEPARATORS.COMMA,
    description: 'fieldNumberSubForm.periodComma',
    value: 'PERIOD_COMMA',
  },
}

/**
 * Returns all number format options for a given field
 */
export const getNumberFormatOptions = (field) => {
  const { thousandSeparator, decimalSeparator } =
    NUMBER_FORMATS[field.number_separator] ?? NUMBER_FORMATS.NO_FORMATTING

  const numberPrefix = field.number_prefix ?? ''
  const numberSuffix = field.number_suffix ?? ''
  const decimalPlaces = field.number_decimal_places ?? undefined
  const allowNegative = field.number_negative ?? false

  return {
    thousandSeparator,
    decimalSeparator,
    numberPrefix,
    numberSuffix,
    decimalPlaces,
    allowNegative,
  }
}

/*
 * FIXME: This function formats a number value according to the field's number format.
 * Value can be a number or a string. If it's a string, it must be in the format
 * of the field's number format. If it's a number, it will be formatted according
 * to the field's number format.
 */
export const formatNumberValue = (
  field,
  value,
  withThousandSeparator = true,
  roundDecimals = true
) => {
  if (value === null || value === undefined || value === '') {
    return ''
  }

  const {
    thousandSeparator,
    decimalSeparator,
    numberPrefix,
    numberSuffix,
    decimalPlaces,
  } = getNumberFormatOptions(field)

  // Parse the input value if it's a string
  let numericValue =
    typeof value === 'string'
      ? parseNumberValue(field, value, roundDecimals)
      : value

  if (numericValue === null) {
    return null
  }

  numericValue = new BigNumber(numericValue)
  if (numericValue.isNaN()) {
    return String(NaN)
  }
  const isNegative = numericValue.isNegative()
  numericValue = numericValue.absoluteValue().toString()

  let locale, localeThousandsSeparator
  if (decimalSeparator === DECIMAL_SEPARATORS.COMMA) {
    locale = 'it-IT'
    localeThousandsSeparator = DECIMAL_SEPARATORS.PERIOD
  } else {
    locale = 'en-US'
    localeThousandsSeparator = DECIMAL_SEPARATORS.COMMA
  }
  // Format the number, but keep all decimal places if roundDecimals is false.
  // For example, filter values are not rounded since the backend doesn't round them.
  const formatter = new Intl.NumberFormat(locale, {
    minimumFractionDigits: decimalPlaces,
    maximumFractionDigits: roundDecimals
      ? decimalPlaces
      : NUMBER_MAX_DECIMAL_PLACES,
    useGrouping: true,
  })
  let formatted = formatter.format(numericValue)

  if (!withThousandSeparator) {
    formatted = formatted.replace(
      new RegExp(`\\${localeThousandsSeparator}`, 'g'),
      ''
    )
  } else if (thousandSeparator !== localeThousandsSeparator) {
    formatted = formatted.replace(
      new RegExp(`\\${localeThousandsSeparator}`, 'g'),
      thousandSeparator
    )
  }

  const sign = isNegative ? '-' : ''
  return `${sign}${numberPrefix}${formatted}${numberSuffix}`.trim()
}

export const parseNumberValue = (field, value, roundDecimals = true) => {
  const { numberPrefix, numberSuffix, decimalSeparator } =
    getNumberFormatOptions(field)

  if (value == null || value === '') {
    return null
  }

  const toBigNumber = (val) => {
    let rounded = val
    if (roundDecimals) {
      rounded = new BigNumber(val).decimalPlaces(
        field.number_decimal_places ?? 0
      )
    }
    return new BigNumber(rounded)
  }

  if (typeof value === 'number' || BigNumber.isBigNumber(value)) {
    return toBigNumber(value)
  }

  let result = value

  // 1. check if the number is negative
  let isNegative = false
  if (result.startsWith('-')) {
    isNegative = field.number_negative
    result = result.substring(1)
  }
  // 2. remove the prefix
  if (numberPrefix && result.startsWith(numberPrefix)) {
    result = result.substring(numberPrefix.length)
  }
  // 3. remove the suffix
  if (numberSuffix && result.endsWith(numberSuffix)) {
    result = result.substring(0, result.length - numberSuffix.length)
  }

  // 5. Match and keep the first decimal separator
  // 6. Keep all digits
  // 7. Remove any additional decimal separators and non-numeric characters
  const firstSep = result.indexOf(decimalSeparator)
  const regex = /[^0-9]/g
  if (firstSep === -1) {
    result = result.replace(regex, '')
  } else {
    const integerPart = result.substring(0, firstSep).replace(regex, '')
    const decimalPart = result.substring(firstSep + 1).replace(regex, '')
    result = `${integerPart}${decimalSeparator}${decimalPart || 0}`
  }
  // Ensure we use a period as the decimal separator before the parsing
  if (decimalSeparator !== '.') {
    result = result.replace(new RegExp(decimalSeparator, 'g'), '.')
  }

  const parsedNumber = toBigNumber(result)
  return parsedNumber.isNaN()
    ? null
    : isNegative
    ? parsedNumber.negated()
    : parsedNumber
}

/**
 * Formats a decimal number sent from the backend according to the field's number
 * format.
 * @param {Object} field - The field object containing number format options.
 * @param {string|number|null} value - The decimal value (with a dot as a decimal
 * separator) to format, can be a string or a number or null.
 * @returns {string} - The number formatted as a string accordingly to the field
 * formatting options, or an empty string if the value is null or empty.
 */
export const formatDecimalNumber = (field, value) => {
  if (value == null || value === '') {
    return ''
  }
  return formatNumberValue(field, new BigNumber(value))
}
