import {
  Timedelta,
  isValidDurationFormat,
  parseValueWithDurationFormat,
  tokenizeDurationFormat,
} from '@baserow/modules/core/utils/duration'

const MS_IN_SEC = 1000
const MS_IN_MIN = 60 * MS_IN_SEC
const MS_IN_HOUR = 60 * MS_IN_MIN
const MS_IN_DAY = 24 * MS_IN_HOUR

describe('tokenizeDurationFormat', () => {
  describe('valid formats', () => {
    const cases = [
      ['h:mm', '1:30', ['hours', 'minutes'], ['1', '30']],
      // literal `:` separators are escaped
      [
        'h:mm:ss',
        '1:23:45',
        ['hours', 'minutes', 'seconds'],
        ['1', '23', '45'],
      ],
      // space-separated tokens
      [
        'd h mm ss',
        '2 3 04 05',
        ['days', 'hours', 'minutes', 'seconds'],
        ['2', '3', '04', '05'],
      ],
      // two-char tokens take precedence over one-char (hh, not h+h)
      ['hh:mm', '12:34', ['hours', 'minutes'], ['12', '34']],
      // arbitrary literal chars (avoid d/h/m/s, which are token letters)
      ['d|h.', '2|5.', ['days', 'hours'], ['2', '5']],
      // leading minus is optional
      ['h:mm', '-1:30', ['hours', 'minutes'], ['1', '30']],
    ]
    test.each(cases)(
      'format %s matches %s into fields %j with groups %j',
      (formatStr, value, expectedFields, expectedGroups) => {
        const result = tokenizeDurationFormat(formatStr)

        expect(result).not.toBeNull()
        expect(result.pattern).toBeInstanceOf(RegExp)
        expect(result.fields).toStrictEqual(expectedFields)
        const match = value.match(result.pattern)
        expect(match).not.toBeNull()
        // match[0] is the full string; capture groups start at index 1.
        expect(match.slice(1)).toStrictEqual(expectedGroups)
      }
    )
  })

  describe('values that do not match the compiled pattern', () => {
    const cases = [
      // anchored to start of string
      ['h:mm', 'prefix 1:30'],
      // anchored to end of string
      ['h:mm', '1:30 trailing'],
      // literal mismatch (`|` in format, `/` in value)
      ['d|h.', '2/5.'],
    ]
    test.each(cases)('format %s does not match %s', (formatStr, value) => {
      const { pattern } = tokenizeDurationFormat(formatStr)

      expect(value.match(pattern)).toBeNull()
    })
  })

  describe('invalid formats return null', () => {
    const repeatedTokens = [
      'h:mm:h', // h repeated
      'mm mm', // mm repeated
      'h hh', // h then hh — both map to "hours"
      'ss s', // ss then s — both map to "seconds"
    ]
    test.each(repeatedTokens)('repeated token in %s', (formatStr) => {
      expect(tokenizeDurationFormat(formatStr)).toBeNull()
    })

    const noTokens = [
      '',
      ':::', // only literals
      '   ', // only whitespace
    ]
    test.each(noTokens)('no duration token in %j', (formatStr) => {
      expect(tokenizeDurationFormat(formatStr)).toBeNull()
    })

    const nonStrings = [null, undefined, 1, 1.5, [], {}, true]
    test.each(nonStrings)('non-string input %p', (value) => {
      expect(tokenizeDurationFormat(value)).toBeNull()
    })
  })
})

describe('isValidDurationFormat', () => {
  const valid = ['h:mm', 'h:mm:ss', 'd h:mm:ss', 'd h mm ss', 'd', 'hh:mm:ss']
  test.each(valid)('returns true for %s', (formatStr) => {
    expect(isValidDurationFormat(formatStr)).toBe(true)
  })

  const invalid = ['', 'h:h', ':::', null, undefined, 123, [], {}]
  test.each(invalid)('returns false for %p', (value) => {
    expect(isValidDurationFormat(value)).toBe(false)
  })
})

describe('parseValueWithDurationFormat', () => {
  describe('valid values', () => {
    const cases = [
      ['1:30', 'h:mm', 1 * MS_IN_HOUR + 30 * MS_IN_MIN],
      ['1:23:45', 'h:mm:ss', 1 * MS_IN_HOUR + 23 * MS_IN_MIN + 45 * MS_IN_SEC],
      [
        '2 3:04:05',
        'd h:mm:ss',
        2 * MS_IN_DAY + 3 * MS_IN_HOUR + 4 * MS_IN_MIN + 5 * MS_IN_SEC,
      ],
      ['3 4', 'd h', 3 * MS_IN_DAY + 4 * MS_IN_HOUR],
      ['-1:30', 'h:mm', -(1 * MS_IN_HOUR + 30 * MS_IN_MIN)],
      // surrounding whitespace is stripped
      ['  1:30  ', 'h:mm', 1 * MS_IN_HOUR + 30 * MS_IN_MIN],
      ['0:00', 'h:mm', 0],
      // the generated regex uses \d+ for every field, so single-digit
      // values are accepted even where the format suggests two digits
      ['1:5', 'h:mm', 1 * MS_IN_HOUR + 5 * MS_IN_MIN],
      // "hh:mm" tokenizes as hh + mm, not h + h + mm
      ['12:34', 'hh:mm', 12 * MS_IN_HOUR + 34 * MS_IN_MIN],
      // 25 hours fits into the resulting Timedelta as 1 day + 1 hour worth of ms
      ['25:00', 'h:mm', 25 * MS_IN_HOUR],
    ]
    test.each(cases)(
      'parses %s with format %s',
      (value, formatStr, expectedMs) => {
        const result = parseValueWithDurationFormat(value, formatStr)

        expect(result).toBeInstanceOf(Timedelta)
        expect(result.ms).toBe(expectedMs)
      }
    )
  })

  describe('invalid input returns null', () => {
    const cases = [
      // value doesn't match the format's literal separator
      ['1.30', 'h:mm'],
      // value has trailing garbage
      ['1:30 extra', 'h:mm'],
      // non-string values
      [null, 'h:mm'],
      [undefined, 'h:mm'],
      [1, 'h:mm'],
      [1.5, 'h:mm'],
      [[], 'h:mm'],
      [{}, 'h:mm'],
      // invalid format strings
      ['1:30', null],
      ['1:30', undefined],
      ['1:30', ''],
      ['1:30', 'h:h'],
      ['1:30', 123],
      ['1:30', ':::'],
    ]
    test.each(cases)('value %p with format %p', (value, formatStr) => {
      expect(parseValueWithDurationFormat(value, formatStr)).toBeNull()
    })
  })
})
