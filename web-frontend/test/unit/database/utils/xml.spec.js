import { parseXML } from '@baserow/modules/database/utils/xml'

describe('test xml utils', () => {
  test('xml parser', () => {
    const [header, xmlData, errors] = parseXML(`
<notes>
  <note>
      <to>Tove</to>
      <from>Jani</from>
      <heading>Reminder</heading>
      <body>Don't forget me this weekend!</body>
  </note>
  <note>
      <heading>Reminder</heading>
      <heading2>Reminder2</heading2>
      <to>Tove</to>
      <from>Jani</from>
      <body>Don't forget me this weekend!</body>
  </note>
</notes>
    `)
    expect(errors.length).toBe(0)
    expect(header.length).toBe(5)
    expect(header[0]).toBe('to')
    expect(header[1]).toBe('from')
    expect(header[2]).toBe('heading')
    expect(header[3]).toBe('body')
    expect(header[4]).toBe('heading2')
    expect(xmlData.length).toBe(2)
    expect(xmlData[0].length).toBe(5)
    expect(xmlData[1].length).toBe(5)
    expect(xmlData[0][0]).toBe('Tove')
    expect(xmlData[0][1]).toBe('Jani')
    expect(xmlData[0][2]).toBe('Reminder')
    expect(xmlData[0][3]).toBe("Don't forget me this weekend!")
    expect(xmlData[0][4]).toBe('')
    expect(xmlData[1][0]).toBe('Tove')
    expect(xmlData[1][1]).toBe('Jani')
    expect(xmlData[1][2]).toBe('Reminder')
    expect(xmlData[1][3]).toBe("Don't forget me this weekend!")
    expect(xmlData[1][4]).toBe('Reminder2')
  })
})
