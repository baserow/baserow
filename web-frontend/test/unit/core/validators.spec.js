import {
  nameContainsNoSpam,
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
    'ｅｖｉｌ．ｃｏｍ',
    'evil\u200b.com',
  ]

  test.each(validNames)('accepts %j', (name) => {
    expect(nameContainsNoUrl(name)).toBe(true)
  })

  test.each(invalidNames)('rejects %j', (name) => {
    expect(nameContainsNoUrl(name)).toBe(false)
  })
})

describe('nameContainsNoSpam', () => {
  const validNames = [
    'Dr. Smith',
    "Mary-Jane O'Neil",
    'Zoë Müller',
    '山田太郎',
    'Team 2026',
    '2025-2026 Budget',
    '12345 Main',
    '🚀 Marketing',
    '🇳🇱 Sales',
    'Area m²',
    'Ｊｏｈｎ',
    '👨\u200d👩\u200d👧 Family',
  ]

  const invalidNames = [
    '🅰🅱🅲-❶❷❸❹❺❻◆⓿◆🅐❶❷',
    '💬🅰🅱🅲-❶❷❸-₁₂₃🅂❹❺.',
    '𝐉𝐨𝐢𝐧 𝐦𝐞 𝐧𝐨𝐰',
    '①②③④⑤⑥',
    '群1234567890聯絡加入',
    '優惠活動1234567890加群12',
    'call 0612345678',
    'call 0\u200b6\u200b1\u200b2\u200b3\u200b4\u200b5\u200b6',
  ]

  test.each(validNames)('accepts %j', (name) => {
    expect(nameContainsNoSpam(name)).toBe(true)
  })

  test.each(invalidNames)('rejects %j', (name) => {
    expect(nameContainsNoSpam(name)).toBe(false)
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
