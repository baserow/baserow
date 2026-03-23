import {
  uuid,
  generateUUID,
  upperCaseFirst,
  slugify,
  isValidURL,
  isValidEmail,
  isSecureURL,
  isNumeric,
  isInteger,
  isSubstringOfStrings,
} from '@baserow/modules/core/utils/string'

describe('test string utils', () => {
  const originalCrypto = globalThis.crypto
  const uuidV4Pattern =
    /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i

  afterEach(() => {
    Object.defineProperty(globalThis, 'crypto', {
      value: originalCrypto,
      configurable: true,
      writable: true,
    })
    vi.restoreAllMocks()
  })

  test('uuid', () => {
    const value = uuid()
    expect(typeof value).toBe('string')
  })

  test('generateUUID uses crypto.randomUUID when available', () => {
    const randomUUID = vi.fn(() => 'test-random-uuid')
    const getRandomValues = vi.fn()

    Object.defineProperty(globalThis, 'crypto', {
      value: { randomUUID, getRandomValues },
      configurable: true,
      writable: true,
    })

    expect(generateUUID()).toBe('test-random-uuid')
    expect(randomUUID).toHaveBeenCalledTimes(1)
    expect(getRandomValues).not.toHaveBeenCalled()
  })

  test('generateUUID uses crypto.getRandomValues when randomUUID is unavailable', () => {
    const getRandomValues = vi.fn((bytes) => {
      bytes.set([
        0x00, 0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77, 0x88, 0x99, 0xaa, 0xbb,
        0xcc, 0xdd, 0xee, 0xff,
      ])
      return bytes
    })

    Object.defineProperty(globalThis, 'crypto', {
      value: { getRandomValues },
      configurable: true,
      writable: true,
    })

    expect(generateUUID()).toBe('00112233-4455-4677-8899-aabbccddeeff')
    expect(getRandomValues).toHaveBeenCalledTimes(1)
  })

  test('generateUUID falls back to Math.random when crypto is unavailable', () => {
    Object.defineProperty(globalThis, 'crypto', {
      value: undefined,
      configurable: true,
      writable: true,
    })

    const mathRandomSpy = vi.spyOn(Math, 'random')

    const value = generateUUID()

    expect(value).toMatch(uuidV4Pattern)
    expect(mathRandomSpy).toHaveBeenCalled()
  })

  test('upperCaseFirst', () => {
    expect(upperCaseFirst('test string')).toBe('Test string')
    expect(upperCaseFirst('Test string')).toBe('Test string')
    expect(upperCaseFirst('TEST string')).toBe('TEST string')
    expect(upperCaseFirst('tEST String')).toBe('TEST String')
    expect(upperCaseFirst('test')).toBe('Test')
    expect(upperCaseFirst('a')).toBe('A')
    expect(upperCaseFirst('A')).toBe('A')
    expect(upperCaseFirst('')).toBe('')
  })

  test('slugify', () => {
    expect(slugify('')).toBe('')
    expect(slugify('test')).toBe('test')
    expect(slugify('This is A test')).toBe('this-is-a-test')
    expect(slugify('/ā/t+?,.;!@')).toBe('a-t')
    expect(slugify('/a&--b/')).toBe('a-and-b')
  })

  test('isValidURL', () => {
    const validURLs = [
      'baserow.io',
      'ftp://baserow.io',
      'git://example.com/',
      'ws://baserow.io',
      'http://baserow.io',
      'https://baserow.io',
      'https://www.baserow.io',
      'HTTP://BASEROW.IO',
      'https://test.nl/test',
      'https://test.nl/test',
      'http://localhost',
      '//localhost',
      'https://test.nl/test?with=a-query&that=has-more',
      'https://test.nl/test',
      "http://-.~_!$&'()*+,;=%40:80%2f@example.com",
      'http://उदाहरण.परीक्षा',
      'http://foo.com/(something)?after=parens',
      'http://142.42.1.1/',
      'http://userid:password@example.com:65535/',
      'http://su--b.valid-----hyphens.com/',
      '//baserow.io/test',
      '127.0.0.1',
      'https://test.nl#test',
      'http://baserow.io/hrscywv4p/image/upload/c_fill,g_faces:center,h_128,w_128/yflwk7vffgwyyenftkr7.png',
      'https://gitlab.com/baserow/baserow/-/issues?row=nice/route',
      'https://web.archive.org/web/20210313191012/https://baserow.io/',
      'mailto:bram@baserow.io?test=test',
    ]

    const invalidURLs = [
      'test',
      'test.',
      'localhost',
      '\nwww.test.nl',
      'www\n.test.nl',
      'www .test.nl',
      ' www.test.nl',
    ]

    for (const invalidUrl of invalidURLs) {
      expect(isValidURL(invalidUrl)).toBe(false)
    }
    for (const validUrl of validURLs) {
      expect(isValidURL(validUrl)).toBe(true)
    }
  })

  test('isValidEmail', () => {
    const invalidEmails = [
      'test@' + 'a'.repeat(246) + '.com',
      '@a',
      'a@',
      'not-an-email',
      'bram.test.nl',
      'invalid_email',
      'invalid@invalid@com',
      '\nhello@gmail.com',
      'asdds asdd@gmail.com',
    ]

    const validEmails = [
      'test@' + 'a'.repeat(245) + '.com',
      'a@a',
      '用户@例子.广告',
      'अजय@डाटा.भारत',
      'квіточка@пошта.укр',
      'χρήστης@παράδειγμα.ελ',
      'Dörte@Sörensen.example.com',
      'коля@пример.рф',
      'bram@localhost',
      'bram@localhost.nl',
      'first_part_underscores_ok@hyphens-ok.com',
      'wierd@[1.1.1.1]',
      'bram.test.test@sub.domain.nl',
      'BRAM.test.test@sub.DOMAIN.nl',
    ]

    for (const invalidEmail of invalidEmails) {
      expect(isValidEmail(invalidEmail)).toBe(false)
    }
    for (const validEmail of validEmails) {
      expect(isValidEmail(validEmail)).toBe(true)
    }
  })

  test('isSecureURL', () => {
    expect(isSecureURL('test')).toBe(false)
    expect(isSecureURL('http://test.nl')).toBe(false)
    expect(isSecureURL('https://test.nl')).toBe(true)
    expect(isSecureURL('HTTPS://test.nl')).toBe(true)
    expect(isSecureURL('https://test.domain.nl?test=test')).toBe(true)
  })

  test('isNumeric', () => {
    expect(isNumeric('a')).toBe(false)
    expect(isNumeric('1.2')).toBe(true)
    expect(isNumeric('1,2')).toBe(false)
    expect(isNumeric('')).toBe(false)
    expect(isNumeric('null')).toBe(false)
    expect(isNumeric('12px')).toBe(false)
    expect(isNumeric('1')).toBe(true)
    expect(isNumeric('9999')).toBe(true)
    expect(isNumeric('-100')).toBe(true)
  })

  test('isInteger', () => {
    expect(isInteger('a')).toBe(false)
    expect(isInteger('1.2')).toBe(false)
    expect(isInteger('1,2')).toBe(false)
    expect(isInteger('')).toBe(false)
    expect(isInteger('null')).toBe(false)
    expect(isInteger('12px')).toBe(false)
    expect(isInteger('1')).toBe(true)
    expect(isInteger('9999')).toBe(true)
    expect(isInteger('-100')).toBe(true)
  })
  test('isSubstringOfStrings', () => {
    expect(isSubstringOfStrings(['hello'], 'hell')).toBe(true)
    expect(isSubstringOfStrings(['test'], 'hell')).toBe(false)
    expect(isSubstringOfStrings(['hello', 'test'], 'hell')).toBe(true)
    expect(isSubstringOfStrings([], 'hell')).toBe(false)
    expect(isSubstringOfStrings(['hello'], '')).toBe(true)
  })
})
