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

export class Timedelta {
  constructor(ms) {
    this.ms = ms
  }
}

// Keep in sync with duration.py::tokenize_duration_format
const DURATION_FORMAT_TOKENS = [
  ['hh', 'hours'],
  ['mm', 'minutes'],
  ['ss', 'seconds'],
  ['d', 'days'],
  ['h', 'hours'],
  ['m', 'minutes'],
  ['s', 'seconds'],
]

const escapeRegExp = (str) => str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')

export const tokenizeDurationFormat = (formatStr) => {
  if (typeof formatStr !== 'string' || formatStr.length === 0) return null

  const pattern = ['^-?']
  const fields = []
  const seen = new Set()
  let i = 0
  while (i < formatStr.length) {
    // A backslash escapes the next character so it is matched/emitted as a
    // literal, even token letters (d/h/m/s/f) or the backslash itself. This
    // lets formats carry literal unit suffixes, e.g. `d\d h\h` -> "1d 2h". A
    // trailing backslash has nothing to escape and is invalid.
    if (formatStr[i] === '\\') {
      if (i + 1 >= formatStr.length) return null
      pattern.push(escapeRegExp(formatStr[i + 1]))
      i += 2
      continue
    }
    // The fractional-seconds token "f" is consumed as a run ("f", "ff", "fff",
    // …) whose length is the precision (mirrors the hh/mm/ss width semantics).
    // It is a distinct field that may appear at most once, and the separator
    // before it stays a literal so arbitrary delimiters work ("ss.fff",
    // "s fff", "mm:ss,ff").
    if (formatStr[i] === 'f') {
      if (seen.has('fraction')) return null
      seen.add('fraction')
      let precision = 0
      while (i < formatStr.length && formatStr[i] === 'f') {
        precision += 1
        i += 1
      }
      fields.push('fraction')
      // capture up to `precision` digits; extra digits won't match
      pattern.push(`(\\d{1,${precision}})`)
      continue
    }
    let matched = false
    for (const [token, field] of DURATION_FORMAT_TOKENS) {
      if (formatStr.startsWith(token, i)) {
        if (seen.has(field)) return null
        seen.add(field)
        fields.push(field)
        pattern.push('(\\d+)')
        i += token.length
        matched = true
        break
      }
    }
    if (!matched) {
      pattern.push(escapeRegExp(formatStr[i]))
      i += 1
    }
  }

  if (fields.length === 0) return null

  pattern.push('$')
  return { pattern: new RegExp(pattern.join('')), fields }
}

export const isValidDurationFormat = (value) =>
  tokenizeDurationFormat(value) !== null

// Return the precision (length of the `f` run) of a validated token format, or
// 0 if it has no fractional token. Walks the format honoring backslash escapes
// so an escaped `\f` literal is not mistaken for the fraction token. Keep in
// sync with duration.py::_fraction_precision.
const fractionPrecision = (formatStr) => {
  let i = 0
  while (i < formatStr.length) {
    if (formatStr[i] === '\\') {
      i += 2
      continue
    }
    if (formatStr[i] === 'f') {
      let precision = 0
      while (i < formatStr.length && formatStr[i] === 'f') {
        precision += 1
        i += 1
      }
      return precision
    }
    i += 1
  }
  return 0
}

export const parseValueWithDurationFormat = (value, formatStr) => {
  if (typeof value !== 'string') return null
  const tokenized = tokenizeDurationFormat(formatStr)
  if (tokenized === null) return null

  const stripped = value.trim()
  const negative = stripped.startsWith('-')
  const match = stripped.match(tokenized.pattern)
  if (match === null) return null

  const parts = { days: 0, hours: 0, minutes: 0, seconds: 0 }
  let fractionMs = 0
  tokenized.fields.forEach((field, idx) => {
    const group = match[idx + 1]
    if (field === 'fraction') {
      // The captured digits are a positional decimal: "5" -> 0.5,
      // "05" -> 0.05, "234" -> 0.234.
      fractionMs = (parseInt(group, 10) / 10 ** group.length) * 1000
    } else {
      parts[field] = parseInt(group, 10)
    }
  })

  let ms =
    parts.days * SECS_IN_DAY * 1000 +
    parts.hours * SECS_IN_HOUR * 1000 +
    parts.minutes * SECS_IN_MIN * 1000 +
    parts.seconds * 1000 +
    fractionMs
  if (negative) ms = -ms
  return new Timedelta(ms)
}

// Keep in sync with duration.py::format_value_with_duration_format
export const formatValueWithDurationFormat = (value, formatStr) => {
  if (!(value instanceof Timedelta)) return null
  const tokenized = tokenizeDurationFormat(formatStr)
  if (tokenized === null) return null

  const fieldSet = new Set(tokenized.fields)
  const negative = value.ms < 0
  const absMs = Math.abs(value.ms)

  // Precision is the number of `f`s in the format, or 0 for integer-second
  // formats (no fraction token).
  const precision = fieldSet.has('fraction') ? fractionPrecision(formatStr) : 0

  // Round the total to the target precision *before* decomposing, so a
  // rounded-up value carries across fields: 59.9996 at precision 3 -> 60.000
  // rolls seconds into minutes, and 59.6 at precision 0 -> 60 rolls into a
  // minute. `Math.round` rounds half up, matching the backend's half-away-from-
  // zero on the absolute value. Keep in sync with duration.py.
  const factor = 10 ** precision
  const total = Math.round((absMs / 1000) * factor) / factor
  const totalSeconds = Math.trunc(total)
  const fractionValue = total - totalSeconds

  let days = 0
  let hours = 0
  let minutes = 0
  let seconds = 0
  if (fieldSet.has('days')) {
    days = Math.trunc(totalSeconds / SECS_IN_DAY)
  }
  if (fieldSet.has('hours')) {
    hours = fieldSet.has('days')
      ? Math.trunc((totalSeconds % SECS_IN_DAY) / SECS_IN_HOUR)
      : Math.trunc(totalSeconds / SECS_IN_HOUR)
  }
  if (fieldSet.has('minutes')) {
    minutes =
      fieldSet.has('hours') || fieldSet.has('days')
        ? Math.trunc((totalSeconds % SECS_IN_HOUR) / SECS_IN_MIN)
        : Math.trunc(totalSeconds / SECS_IN_MIN)
  }
  if (fieldSet.has('seconds')) {
    seconds =
      fieldSet.has('minutes') || fieldSet.has('hours') || fieldSet.has('days')
        ? totalSeconds % SECS_IN_MIN
        : totalSeconds
  }

  const fieldValues = { days, hours, minutes, seconds }
  const out = []
  let i = 0
  while (i < formatStr.length) {
    if (formatStr[i] === '\\') {
      // Escaped literal, emit the next character verbatim. The format is
      // already validated (tokenize succeeded), so a following char exists.
      out.push(formatStr[i + 1])
      i += 2
      continue
    }
    if (formatStr[i] === 'f') {
      // Render the fractional component as `precision` zero-padded digits
      // (mirrors printf's %0width.Nf).
      const digits = Math.round(fractionValue * 10 ** precision)
      out.push(String(digits).padStart(precision, '0'))
      i += precision
      continue
    }
    let matched = false
    for (const [token, field] of DURATION_FORMAT_TOKENS) {
      if (formatStr.startsWith(token, i)) {
        const v = fieldValues[field]
        out.push(token.length === 2 ? String(v).padStart(2, '0') : String(v))
        i += token.length
        matched = true
        break
      }
    }
    if (!matched) {
      out.push(formatStr[i])
      i += 1
    }
  }

  const result = out.join('')
  return negative ? `-${result}` : result
}

const DURATION_PATTERNS = [
  { regex: /^(\d+)\s+years?$/i, unit: 'days', factor: 365 },
  { regex: /^(\d+)\s+months?$/i, unit: 'days', factor: 30 },
  { regex: /^(\d+)\s+weeks?$/i, unit: 'days', factor: 7 },
  { regex: /^(\d+)\s+days?$/i, unit: 'days', factor: 1 },
  { regex: /^(\d+)\s+hours?$/i, unit: 'hours', factor: 1 },
  { regex: /^(\d+)\s+minutes?$/i, unit: 'minutes', factor: 1 },
  { regex: /^(\d+)\s+seconds?$/i, unit: 'seconds', factor: 1 },
]

const UNIT_TO_MS = {
  days: SECS_IN_DAY * 1000,
  hours: SECS_IN_HOUR * 1000,
  minutes: SECS_IN_MIN * 1000,
  seconds: 1000,
}

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

// Maps each field DURATION_FORMATS key to the equivalent token-engine format
// consumed by formatValueWithDurationFormat. The `s`-fraction forms become `f`
// runs, and the `d`-prefixed display formats use backslash-escaped literal unit
// letters (e.g. `d\d h\h` -> "1d 2h"), which the token engine cannot emit
// otherwise. Keep in sync with duration.py::DURATION_TOKEN_FORMATS.
const DURATION_TOKEN_FORMATS = {
  [H_M]: 'h:mm',
  [H_M_S]: 'h:mm:ss',
  [H_M_S_S]: 'h:mm:ss.f',
  [H_M_S_SS]: 'h:mm:ss.ff',
  [H_M_S_SSS]: 'h:mm:ss.fff',
  [D_H]: 'd\\d h\\h',
  [D_H_M]: 'd\\d h:mm',
  [D_H_M_S]: 'd\\d h:mm:ss',
  [D_H_M_NO_COLONS]: 'd\\d h\\h mm\\m',
  [D_H_M_S_NO_COLONS]: 'd\\d h\\h mm\\m ss\\s',
}

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
    } catch (err) {
      /* empty */
    }

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

export const parseDurationString = (value) => {
  if (
    value === null ||
    value === undefined ||
    value === '' ||
    (typeof value !== 'string' && !Number.isFinite(value))
  ) {
    return null
  }

  const seconds = parseDurationValue(value, MOST_ACCURATE_DURATION_FORMAT)
  if (seconds !== null) {
    return new Timedelta(seconds * 1000)
  }

  if (typeof value !== 'string') return null
  for (const { regex, unit, factor } of DURATION_PATTERNS) {
    const match = value.trim().match(regex)
    if (match) {
      const amount = parseInt(match[1], 10) * factor
      return new Timedelta(amount * UNIT_TO_MS[unit])
    }
  }
  return null
}

/**
 * It formats the given duration value (a number of seconds) using the given
 * format.
 *
 * Thin adapter over the token formatter (`formatValueWithDurationFormat`), which
 * is the single source of truth for duration display. It converts the seconds
 * value to a `Timedelta` (ms) and translates the field's DURATION_FORMATS key to
 * the equivalent token format first.
 */
export const formatDurationValue = (value, format) => {
  if (value === null || value === undefined || value === '') {
    return ''
  }
  return formatValueWithDurationFormat(
    new Timedelta(value * 1000),
    DURATION_TOKEN_FORMATS[format]
  )
}
