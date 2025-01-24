import _ from 'lodash'

const MOST_ACCURATE_DURATION_FORMAT = 'h:mm:ss.sss'
// taken from backend timedelta.max.total_seconds() == 1_000_000_000 days
export const MAX_BACKEND_DURATION_VALUE_NUMBER_OF_SECS = 86400000000000
export const MIN_BACKEND_DURATION_VALUE_NUMBER_OF_SECS =
  MAX_BACKEND_DURATION_VALUE_NUMBER_OF_SECS * -1
export const DEFAULT_DURATION_FORMAT = 'h:mm'

const D_H = 'd h'
const D_H_M = 'd h:mm'
const D_H_M_S = 'd h:mm:ss'
const H_M = 'h:mm'
const H_M_S = 'h:mm:ss'
const H_M_S_S = 'h:mm:ss.s'
const H_M_S_SS = 'h:mm:ss.ss'
const H_M_S_SSS = 'h:mm:ss.sss'
const D_H_M_NO_COLONS = 'd h mm' // 1d2h3m
const D_H_M_S_NO_COLONS = 'd h mm ss' // 1d2h3m4s

const SECS_IN_DAY = 86400
const SECS_IN_HOUR = 3600
const SECS_IN_MIN = 60

function totalSecs({ secs = null, mins = null, hours = null, days = null }) {
  return (
    parseInt(days || 0) * SECS_IN_DAY +
    parseInt(hours || 0) * SECS_IN_HOUR +
    parseInt(mins || 0) * SECS_IN_MIN +
    parseFloat(secs || 0.0)
  )
}

/** DURATION_REGEXPS
 *
 * A map of regexps to parse input values. Input values are normalized into seconds.
 *
 * Input value semantics may change depending on duration format selection. In
 *  some cases the same values may mean hours or minutes, depending on a format context.
 *  This mapping helps managing this aspect.
 *
 * @type {Map<RegExp, {string: (function({int, int, int, int}): int)}>}
 */
const DURATION_REGEXPS = new Map([
  [
    // 1d 10h 20m 30s
    /^((?<days>\d+)(?:d\s*))?((?<hours>\d+)(?:h\s*))?((?<mins>\d+)(?:m\s*))?((?<secs>\d+|\d+\.\d+)(?:s\s*))?$/,
    {
      default: ({ days, hours, mins, secs }) =>
        totalSecs({ days, hours, mins, secs }),
    },
  ],
  [
    // 1d 12:13:14.123
    /^(\d+)(?:d\s*|\s+)(\d+):(\d+):(\d+|\d+\.\d+)$/,
    {
      default: (days, hours, mins, secs) =>
        totalSecs({ days, hours, mins, secs }),
    },
  ],
  [
    // 1:11:12.134
    /^(\d+):(\d+):(\d+|\d+\.\d+)$/,
    {
      default: (hours, mins, secs) => totalSecs({ hours, mins, secs }),
    },
  ],
  [
    // 1d 12:13
    /^(\d+)(?:d\s*|\s+)(\d+):(\d+)$/,
    {
      [D_H]: (days, hours, mins) => totalSecs({ days, hours, mins }),
      [D_H_M]: (days, hours, mins) => totalSecs({ days, hours, mins }),
      [D_H_M_NO_COLONS]: (days, hours, mins) =>
        totalSecs({ days, hours, mins }),
      default: (days, mins, secs) => totalSecs({ days, mins, secs }),
    },
  ],
  [
    // 1d 11:12 -> 1 00:11:12
    /^(\d+)(?:d\s*|\s+)(\d+):(\d+\.\d+)$/,
    { default: (days, mins, secs) => totalSecs({ days, mins, secs }) },
  ],
  [
    // 123h -> 5d 3h
    /^(\d+)h$/,
    { default: (hours) => totalSecs({ hours }) },
  ],
  [
    // 1d 12h
    /^(\d+)(?:d\s*|\s+)(\d+)h$/,
    {
      default: (days, hours) => totalSecs({ days, hours }),
    },
  ],
  [
    // 123d
    /^(\d+)d$/,
    { default: (days) => totalSecs({ days }) },
  ],
  [
    // 1d 12
    /^(\d+)(?:d\s*|\s+)(\d+)$/,
    {
      [D_H]: (days, hours) => totalSecs({ days, hours }),
      [D_H_M]: (days, mins) => totalSecs({ days, mins }),
      [H_M]: (days, mins) => totalSecs({ days, mins }),
      [D_H_M_NO_COLONS]: (days, mins) => totalSecs({ days, mins }),
      default: (days, secs) => totalSecs({ days, secs }),
    },
  ],
  [
    // 1d 123.234
    /^(\d+)(?:d\s*|\s+)(\d+\.\d+)$/,
    { default: (days, secs) => totalSecs({ days, secs }) },
  ],
  [
    // 11:12
    /^(\d+):(\d+)$/,
    {
      [D_H]: (hours, mins) => totalSecs({ hours, mins }),
      [D_H_M]: (hours, mins) => totalSecs({ hours, mins }),
      [H_M]: (hours, mins) => totalSecs({ hours, mins }),
      [D_H_M_NO_COLONS]: (hours, mins) => totalSecs({ hours, mins }),
      default: (mins, secs) => totalSecs({ mins, secs }),
    },
  ],
  [
    // 123:12.123 -> 2h3m12s
    /^(\d+):(\d+\.\d+)$/,
    { default: (mins, secs) => totalSecs({ mins, secs }) },
  ],
  [
    // 123.2134
    /^(\d+\.\d+)$/,
    { default: (secs) => totalSecs({ secs }) },
  ],
  [
    // 123
    /^(\d+)$/,
    {
      [D_H]: (hours) => totalSecs({ hours }),
      [D_H_M]: (mins) => totalSecs({ mins }),
      [H_M]: (mins) => totalSecs({ mins }),
      [D_H_M_NO_COLONS]: (mins) => totalSecs({ mins }),
      default: (secs) => totalSecs({ secs }),
    },
  ],
])

// Map guarantees the order of the entries
export const DURATION_FORMATS = new Map([
  [
    H_M,
    {
      description: 'h:mm (1:23)',
      example: '1:23',
      toString(d, h, m, s) {
        return `${d * 24 + h}:${m.toString().padStart(2, '0')}`
      },
      round: (value) => Math.round(value / 60) * 60,
    },
  ],
  [
    H_M_S,
    {
      description: 'h:mm:ss (1:23:40)',
      example: '1:23:40',
      toString(d, h, m, s) {
        return `${d * 24 + h}:${m.toString().padStart(2, '0')}:${s
          .toFixed(0)
          .padStart(2, '0')}`
      },
      round: (value) => Math.round(value),
    },
  ],
  [
    H_M_S_S,
    {
      description: 'h:mm:ss.s (1:23:40.0)',
      example: '1:23:40.0',
      toString(d, h, m, s) {
        return `${d * 24 + h}:${m.toString().padStart(2, '0')}:${s
          .toFixed(1)
          .padStart(4, '0')}`
      },
      round: (value) => Math.round(value * 10) / 10,
    },
  ],
  [
    H_M_S_SS,
    {
      description: 'h:mm:ss.ss (1:23:40.00)',
      example: '1:23:40.00',
      toString(d, h, m, s) {
        return `${d * 24 + h}:${m.toString().padStart(2, '0')}:${s
          .toFixed(2)
          .padStart(5, '0')}`
      },
      round: (value) => Math.round(value * 100) / 100,
    },
  ],
  [
    H_M_S_SSS,
    {
      description: 'h:mm:ss.sss (1:23:40.000)',
      example: '1:23:40.000',
      toString(d, h, m, s) {
        return `${d * 24 + h}:${m.toString().padStart(2, '0')}:${s
          .toFixed(3)
          .padStart(6, '0')}`
      },
      round: (value) => Math.round(value * 1000) / 1000,
    },
  ],
  [
    D_H,
    {
      description: 'd h (1d 2h)',
      example: '1d 2h',
      toString(d, h, m, s) {
        return `${d}d ${h}h`
      },
      round: (value) => Math.round(value / 3600) * 3600,
    },
  ],
  [
    D_H_M,
    {
      description: 'd h:mm (1d 2:34)',
      example: '1d 2:34',
      toString(d, h, m, s) {
        return `${d}d ${h}:${m.toString().padStart(2, '0')}`
      },
      round: (value) => Math.round(value / 60) * 60,
    },
  ],
  [
    D_H_M_S,
    {
      description: 'd h:mm:ss (1d 2:34:56)',
      example: '1d 2:34:56',
      toString(d, h, m, s) {
        return `${d}d ${h}:${m.toString().padStart(2, '0')}:${s
          .toFixed(0)
          .padStart(2, '0')}`
      },
      round: (value) => Math.round(value),
    },
  ],
  [
    D_H_M_NO_COLONS,
    {
      description: 'd h m (1d 2h 3m)',
      example: '1d 2h 3m',
      toString(d, h, m, s) {
        return `${d}d ${h}h ${m.toString().padStart(2, '0')}m`
      },
      // round to a minute
      round: (value) => Math.round(value / 60) * 60,
    },
  ],
  [
    D_H_M_S_NO_COLONS,
    {
      description: 'd h m s (1d 2h 3m 4s)',
      example: '1d 2h 3m 4s',
      toString(d, h, m, s) {
        return `${d}d ${h}h ${m.toString().padStart(2, '0')}m ${s
          .toFixed(0)
          .padStart(2, '0')}s`
      },
      round: (value) => Math.round(value),
    },
  ],
])

export const roundDurationValueToFormat = (value, format) => {
  if (value === null) {
    return null
  }

  const durationFormatOptions = DURATION_FORMATS.get(format)
  if (!durationFormatOptions) {
    throw new Error(`Unknown duration format ${format}`)
  }
  return durationFormatOptions.round(value)
}

/**
 * It tries to parse the input value using the given format.
 * If the input value does not match the format, it tries to parse it using
 * the most accurate format if strict is false, otherwise it throws an error.
 */
export const parseDurationValue = (
  inputValue,
  format = MOST_ACCURATE_DURATION_FORMAT
) => {
  if (inputValue === null || inputValue === undefined || inputValue === '') {
    return null
  }

  // If the value is a number, we assume it's already in seconds (i.e. from the backend).
  if (Number.isFinite(inputValue)) {
    return inputValue
  }

  let multiplier = 1
  if (inputValue.startsWith('-')) {
    multiplier = -1
    inputValue = inputValue.substring(1)
  }
  for (const [fmtRegExp, formatFuncs] of DURATION_REGEXPS) {
    let matchedGroups = {}
    // exec may be null, which will throw an exception
    try {
      matchedGroups = fmtRegExp.exec(inputValue).groups
    } catch (err) {}

    const match = inputValue.match(fmtRegExp)
    const formatFunc = formatFuncs[format] || formatFuncs.default

    // the regex is using named groups, so the handler function should too
    if (!_.isEmpty(matchedGroups)) {
      return formatFunc(matchedGroups) * multiplier
    }
    // no named groups, so we use positional args
    if (match) {
      return formatFunc(...match.slice(1)) * multiplier
    }
  }
  return null
}

/**
 * It formats the given duration value using the given format.
 */
export const formatDurationValue = (value, format) => {
  if (value === null || value === undefined || value === '') {
    return ''
  }
  let sign = ''
  if (value < 0) {
    sign = '-'
    value = -1 * value
  }
  const days = Math.floor(value / 86400)
  const hours = Math.floor((value % 86400) / 3600)
  const mins = Math.floor((value % 3600) / 60)
  const secs = value % 60

  const formatFunc = DURATION_FORMATS.get(format).toString
  return `${sign}${formatFunc(days, hours, mins, secs)}`
}
