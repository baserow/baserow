import { nameContainsNoUrl } from '@baserow/modules/core/validators'

describe('nameContainsNoUrl', () => {
  const validNames = [
    'Dr. Smith',
    'St. John',
    'J.R.R. Tolkien',
    'Mary-Jane O’Neil',
    "Mary-Jane O'Neil",
    'Anne-Marie',
    'Bram',
  ]

  const invalidNames = [
    'POSHMARK! Your account has been blocked: poshmark-helps.com',
    'Your account has been blocked. Verify again: x.gd/2Bqbt',
    'www.evil.com',
    'http://x',
    'https://evil.com',
    'A.Smith',
    'bad\nname',
    'bad\tname',
  ]

  test.each(validNames)('accepts %j', (name) => {
    expect(nameContainsNoUrl(name)).toBe(true)
  })

  test.each(invalidNames)('rejects %j', (name) => {
    expect(nameContainsNoUrl(name)).toBe(false)
  })
})
