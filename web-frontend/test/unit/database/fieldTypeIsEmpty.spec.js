import { TestApp } from '@baserow/test/helpers/testApp'
import {
  TextFieldType,
  DurationFieldType,
  LinkRowFieldType,
} from '@baserow/modules/database/fieldTypes'

// `isEmpty` is shared by the conditional-visibility filters and required form
// validation, so the two stay in sync with each other and with the backend.

const linkRowField = { id: 1, type: 'link_row' }
const textField = { id: 2, type: 'text' }
const durationField = { id: 3, type: 'duration', duration_format: 'h:mm' }

describe('FieldType.isEmpty', () => {
  let testApp = null
  let app = null

  beforeEach(() => {
    testApp = new TestApp()
    app = testApp.store.$app
  })

  afterEach(() => {
    testApp.afterEach()
  })

  test('an empty text value is empty', () => {
    const fieldType = new TextFieldType({ app })
    expect(fieldType.isEmpty(textField, '')).toBe(true)
    expect(fieldType.isEmpty(textField, 'hello')).toBe(false)
  })

  test('an empty duration value is empty (regression #5422/#5469)', () => {
    const fieldType = new DurationFieldType({ app })
    expect(fieldType.isEmpty(durationField, '')).toBe(true)
    expect(fieldType.isEmpty(durationField, null)).toBe(true)
  })

  describe('link_row (selection semantics, matching the backend)', () => {
    let fieldType = null

    beforeEach(() => {
      fieldType = new LinkRowFieldType({ app })
    })

    test('no selection is empty', () => {
      expect(fieldType.isEmpty(linkRowField, [])).toBe(true)
      expect(fieldType.isEmpty(linkRowField, null)).toBe(true)
    })

    test('a placeholder slot without a real id is empty', () => {
      expect(fieldType.isEmpty(linkRowField, [{ id: false, value: '' }])).toBe(
        true
      )
    })

    test('a picked row with an empty primary is NOT empty', () => {
      // A picked row is a real link, so it is not empty even with an empty
      // primary. The backend treats it the same way.
      expect(fieldType.isEmpty(linkRowField, [{ id: 42, value: '' }])).toBe(
        false
      )
    })

    test('a picked row with a primary value is NOT empty', () => {
      expect(
        fieldType.isEmpty(linkRowField, [{ id: 42, value: 'Hello' }])
      ).toBe(false)
    })
  })
})
