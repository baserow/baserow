import {
  Timedelta,
  formatValueWithDurationFormat,
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
      // fractional-seconds run with a dot separator
      [
        'h:mm:ss.fff',
        '1:23:45.678',
        ['hours', 'minutes', 'seconds', 'fraction'],
        ['1', '23', '45', '678'],
      ],
      // single `f` accepts a single fractional digit
      ['ss.f', '45.6', ['seconds', 'fraction'], ['45', '6']],
      // the separator before `f` is a literal, so non-dot delimiters work
      ['s fff', '1 234', ['seconds', 'fraction'], ['1', '234']],
      [
        'mm:ss,ff',
        '01:02,34',
        ['minutes', 'seconds', 'fraction'],
        ['01', '02', '34'],
      ],
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
      'ss.f.f', // fraction run appears twice
      'f.fff', // fraction run appears twice
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
  const valid = [
    'h:mm',
    'h:mm:ss',
    'd h:mm:ss',
    'd h mm ss',
    'd',
    'hh:mm:ss',
    'h:mm:ss.f',
    'h:mm:ss.ff',
    'h:mm:ss.fff',
    's fff',
  ]
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
      // fractional seconds: digits are a positional decimal
      [
        '1:23:45.678',
        'h:mm:ss.fff',
        1 * MS_IN_HOUR + 23 * MS_IN_MIN + 45 * MS_IN_SEC + 678,
      ],
      // "5" at precision 1 is 0.5s, not 0.05s
      ['0:00:00.5', 'h:mm:ss.f', 500],
      // "05" is 0.05s
      ['0:00:00.05', 'h:mm:ss.ff', 50],
      // non-dot separator before the fraction
      ['1 234', 's fff', MS_IN_SEC + 234],
      // negative carries the sub-second component
      ['-0:00:01.250', 'h:mm:ss.fff', -(MS_IN_SEC + 250)],
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

describe('formatValueWithDurationFormat', () => {
  describe('valid durations', () => {
    const cases = [
      [new Timedelta(MS_IN_HOUR + 30 * MS_IN_MIN), 'h:mm', '1:30'],
      [
        new Timedelta(MS_IN_HOUR + 23 * MS_IN_MIN + 45 * MS_IN_SEC),
        'h:mm:ss',
        '1:23:45',
      ],
      [
        new Timedelta(
          2 * MS_IN_DAY + 3 * MS_IN_HOUR + 4 * MS_IN_MIN + 5 * MS_IN_SEC
        ),
        'd h:mm:ss',
        '2 3:04:05',
      ],
      [new Timedelta(3 * MS_IN_DAY + 4 * MS_IN_HOUR), 'd h', '3 4'],
      // h-only rollup: 1d 2h → 26 total hours
      [new Timedelta(MS_IN_DAY + 2 * MS_IN_HOUR), 'h', '26'],
      // mm-only rollup: 1h 30m → 90 total minutes
      [new Timedelta(MS_IN_HOUR + 30 * MS_IN_MIN), 'mm', '90'],
      // mm:ss rollup: 1h 30m → 90 minutes, 0 seconds
      [new Timedelta(MS_IN_HOUR + 30 * MS_IN_MIN), 'mm:ss', '90:00'],
      // ss-only rollup: 5m → 300 total seconds
      [new Timedelta(5 * MS_IN_MIN), 'ss', '300'],
      // within-day hours when d is present: 25h → 1d 1h
      [new Timedelta(25 * MS_IN_HOUR + 30 * MS_IN_MIN), 'd h:mm', '1 1:30'],
      // without d, hours roll up: 25h → 25 total hours
      [new Timedelta(25 * MS_IN_HOUR + 30 * MS_IN_MIN), 'h:mm', '25:30'],
      // negative values get a leading minus
      [new Timedelta(-(MS_IN_HOUR + 30 * MS_IN_MIN)), 'h:mm', '-1:30'],
      [new Timedelta(-(MS_IN_HOUR + 30 * MS_IN_MIN)), 'mm:ss', '-90:00'],
      // zero
      [new Timedelta(0), 'h:mm', '0:00'],
      [new Timedelta(0), 'd h:mm:ss', '0 0:00:00'],
      // two-char tokens are zero-padded; one-char are not
      [new Timedelta(MS_IN_HOUR + 5 * MS_IN_MIN), 'h:mm', '1:05'],
      [new Timedelta(MS_IN_HOUR + 5 * MS_IN_MIN), 'hh:mm', '01:05'],
      // arbitrary literal chars are preserved
      [new Timedelta(2 * MS_IN_DAY + 5 * MS_IN_HOUR), 'd|h.', '2|5.'],
      // integer-second formats (no fraction token) round to whole seconds
      // rather than truncating: 1.5s → "2", 1.4s → "1"
      [new Timedelta(1500), 's', '2'],
      [new Timedelta(1400), 's', '1'],
      // rounding is half up, so 0.5s → "1"
      [new Timedelta(500), 's', '1'],
      [new Timedelta(-500), 's', '-1'],
      // integer rounding carries across fields: 59.6s → 1:00
      [new Timedelta(59600), 'mm:ss', '01:00'],
      // 59m 59.6s → 1:00:00
      [
        new Timedelta(59 * MS_IN_MIN + 59 * MS_IN_SEC + 600),
        'h:mm:ss',
        '1:00:00',
      ],
      // fractional seconds rendered zero-padded to the format precision
      [
        new Timedelta(MS_IN_HOUR + 23 * MS_IN_MIN + 45 * MS_IN_SEC + 678),
        'h:mm:ss.fff',
        '1:23:45.678',
      ],
      // 0.5s at precision 1 → "5"; at precision 3 → "500"
      [new Timedelta(500), 'ss.f', '00.5'],
      [new Timedelta(500), 'ss.fff', '00.500'],
      // 0.05s → "05" at precision 2
      [new Timedelta(50), 'ss.ff', '00.05'],
      // non-dot separator preserved on output
      [new Timedelta(MS_IN_SEC + 234), 's fff', '1 234'],
      // rounding up carries across fields: 59.9996 → 1:00.000
      [new Timedelta(59999.6), 'mm:ss.fff', '01:00.000'],
      // carry that rolls all the way over: 59:59.9996 → 1:00:00.000
      [
        new Timedelta(59 * MS_IN_MIN + 59 * MS_IN_SEC + 999.6),
        'h:mm:ss.fff',
        '1:00:00.000',
      ],
      // values beyond the precision are rounded, not truncated
      [new Timedelta(MS_IN_SEC + 236), 'ss.ff', '01.24'],
      // negative fractional value keeps the sign
      [new Timedelta(-(MS_IN_SEC + 250)), 'ss.fff', '-01.250'],
    ]
    test.each(cases)(
      'formats %p with format %s as %s',
      (value, formatStr, expected) => {
        expect(formatValueWithDurationFormat(value, formatStr)).toBe(expected)
      }
    )
  })

  describe('invalid input returns null', () => {
    const cases = [
      // non-Timedelta values
      [null, 'h:mm'],
      [undefined, 'h:mm'],
      [1, 'h:mm'],
      [1.5, 'h:mm'],
      ['1:30', 'h:mm'],
      [[], 'h:mm'],
      [{}, 'h:mm'],
      // invalid format strings
      [new Timedelta(MS_IN_HOUR), null],
      [new Timedelta(MS_IN_HOUR), undefined],
      [new Timedelta(MS_IN_HOUR), ''],
      [new Timedelta(MS_IN_HOUR), 'h:h'],
      [new Timedelta(MS_IN_HOUR), 123],
      [new Timedelta(MS_IN_HOUR), ':::'],
    ]
    test.each(cases)('value %p with format %p', (value, formatStr) => {
      expect(formatValueWithDurationFormat(value, formatStr)).toBeNull()
    })
  })

  describe('parsed format returns correct duration', () => {
    const cases = [
      [new Timedelta(MS_IN_HOUR + 30 * MS_IN_MIN), 'h:mm'],
      [new Timedelta(MS_IN_HOUR + 23 * MS_IN_MIN + 45 * MS_IN_SEC), 'h:mm:ss'],
      [
        new Timedelta(
          2 * MS_IN_DAY + 3 * MS_IN_HOUR + 4 * MS_IN_MIN + 5 * MS_IN_SEC
        ),
        'd h:mm:ss',
      ],
      [new Timedelta(-(MS_IN_HOUR + 30 * MS_IN_MIN)), 'h:mm'],
      [new Timedelta(25 * MS_IN_HOUR + 30 * MS_IN_MIN), 'h:mm'],
      [new Timedelta(MS_IN_HOUR + 30 * MS_IN_MIN), 'mm:ss'],
      // fractional formats round-trip when the value fits the precision
      [
        new Timedelta(MS_IN_HOUR + 23 * MS_IN_MIN + 45 * MS_IN_SEC + 678),
        'h:mm:ss.fff',
      ],
      [new Timedelta(MS_IN_SEC + 500), 'ss.f'],
      [new Timedelta(MS_IN_SEC + 234), 's fff'],
      [new Timedelta(-(MS_IN_SEC + 250)), 'ss.fff'],
    ]
    test.each(cases)('%p with %s', (duration, formatStr) => {
      const formatted = formatValueWithDurationFormat(duration, formatStr)
      const reparsed = parseValueWithDurationFormat(formatted, formatStr)
      expect(reparsed).toStrictEqual(duration)
    })
  })
})
