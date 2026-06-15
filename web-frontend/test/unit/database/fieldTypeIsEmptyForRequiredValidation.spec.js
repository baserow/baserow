import { TestApp } from '@baserow/test/helpers/testApp'
import {
  TextFieldType,
  DurationFieldType,
  LinkRowFieldType,
} from '@baserow/modules/database/fieldTypes'

// `isEmptyForRequiredValidation` answers "would a required field be considered
// unfilled?". It defaults to `isEmpty`, but link_row overrides it with
// presence semantics so that picking a row whose primary is empty still
// satisfies a required field (while `isEmpty` itself keeps treating that row as
// empty for the conditional-visibility filters).

const linkRowField = { id: 1, type: 'link_row' }
const textField = { id: 2, type: 'text' }
const durationField = { id: 3, type: 'duration', duration_format: 'h:mm' }

describe('isEmptyForRequiredValidation', () => {
  let testApp = null
  let app = null

  beforeEach(() => {
    testApp = new TestApp()
    app = testApp.store.$app
  })

  afterEach(() => {
    testApp.afterEach()
  })

  test('defaults to isEmpty for a text field', () => {
    const fieldType = new TextFieldType({ app })
    expect(fieldType.isEmptyForRequiredValidation(textField, '')).toBe(true)
    expect(fieldType.isEmptyForRequiredValidation(textField, 'hello')).toBe(
      false
    )
  })

  test('treats an empty duration value as missing (regression #5422/#5469)', () => {
    const fieldType = new DurationFieldType({ app })
    expect(fieldType.isEmptyForRequiredValidation(durationField, '')).toBe(true)
    expect(fieldType.isEmptyForRequiredValidation(durationField, null)).toBe(
      true
    )
  })

  describe('link_row override (presence semantics)', () => {
    let fieldType = null

    beforeEach(() => {
      fieldType = new LinkRowFieldType({ app })
    })

    test('no selection is missing', () => {
      expect(fieldType.isEmptyForRequiredValidation(linkRowField, [])).toBe(
        true
      )
    })

    test('a placeholder slot without a real id is missing', () => {
      expect(
        fieldType.isEmptyForRequiredValidation(linkRowField, [
          { id: false, value: '' },
        ])
      ).toBe(true)
    })

    test('a picked row with an empty primary is NOT missing', () => {
      expect(
        fieldType.isEmptyForRequiredValidation(linkRowField, [
          { id: 42, value: '' },
        ])
      ).toBe(false)
    })

    test('a picked row with a primary value is NOT missing', () => {
      expect(
        fieldType.isEmptyForRequiredValidation(linkRowField, [
          { id: 42, value: 'Hello' },
        ])
      ).toBe(false)
    })

    test('isEmpty still treats a picked empty-primary row as empty (filters unchanged)', () => {
      // The conditional-visibility filters rely on this staying true.
      expect(fieldType.isEmpty(linkRowField, [{ id: 42, value: '' }])).toBe(
        true
      )
    })
  })
})
