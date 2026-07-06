import {
  nameContainsNoUrl,
  nameIsNotEmail,
} from '@baserow/modules/core/validators'

describe('nameContainsNoUrl', () => {
  const validNames = [
    'Dr. Smith',
    'St. John',
    'J.R.R. Tolkien',
    'Mary-Jane O’Neil',
    "Mary-Jane O'Neil",
    'Anne-Marie',
    'Bram',
    'J.Smith',
    'A.Merkel',
    'John.Smith',
    'O.J.Simpson',
    'tech.something',
    'something.AI',
    'b.something',
    'startup.ai',
  ]

  const invalidNames = [
    'SOMETHING! Your account has been blocked: something-helps.com',
    'Your account has been blocked. Verify again: x.gd/bot',
    'www.evil.com',
    'http://x',
    'https://evil.com',
    'scam.xyz',
    'evil.click',
    'unknown-tld.weirdtld/path',
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

describe('nameIsNotEmail', () => {
  test.each(['J.Smith', 'Dr. Smith', 'Bram', 'name with @ in it'])(
    'accepts %j',
    (name) => {
      expect(nameIsNotEmail(name)).toBe(true)
    }
  )

  test.each(['john.smith@gmail.com', 'user@example.org', ' user@example.org '])(
    'rejects %j',
    (name) => {
      expect(nameIsNotEmail(name)).toBe(false)
    }
  )
})
