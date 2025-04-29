import {
  uuid,
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
  test('test uuid', () => {
    const value = uuid()
    expect(typeof value).toBe('string')
  })

  test('test upperCaseFirst', () => {
    expect(upperCaseFirst('test string')).toBe('Test string')
    expect(upperCaseFirst('Test string')).toBe('Test string')
    expect(upperCaseFirst('TEST string')).toBe('TEST string')
    expect(upperCaseFirst('tEST String')).toBe('TEST String')
    expect(upperCaseFirst('test')).toBe('Test')
    expect(upperCaseFirst('a')).toBe('A')
    expect(upperCaseFirst('A')).toBe('A')
    expect(upperCaseFirst('')).toBe('')
  })

  test('test slugify', () => {
    expect(slugify('')).toBe('')
    expect(slugify('test')).toBe('test')
    expect(slugify('This is A test')).toBe('this-is-a-test')
    expect(slugify('/ā/t+?,.;!@')).toBe('a-t')
    expect(slugify('/a&--b/')).toBe('a-and-b')
  })

  test('test isValidURL', () => {
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

  test('test isValidEmail', () => {
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

  test('test isSecureURL', () => {
    expect(isSecureURL('test')).toBe(false)
    expect(isSecureURL('http://test.nl')).toBe(false)
    expect(isSecureURL('https://test.nl')).toBe(true)
    expect(isSecureURL('HTTPS://test.nl')).toBe(true)
    expect(isSecureURL('https://test.domain.nl?test=test')).toBe(true)
  })

  test('test isNumeric', () => {
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

  test('test isInteger', () => {
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
  test('test isSubstringOfStrings', () => {
    expect(isSubstringOfStrings(['hello'], 'hell')).toBe(true)
    expect(isSubstringOfStrings(['test'], 'hell')).toBe(false)
    expect(isSubstringOfStrings(['hello', 'test'], 'hell')).toBe(true)
    expect(isSubstringOfStrings([], 'hell')).toBe(false)
    expect(isSubstringOfStrings(['hello'], '')).toBe(true)
  })
})
