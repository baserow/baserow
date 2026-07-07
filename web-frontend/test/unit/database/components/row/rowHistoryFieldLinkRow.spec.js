import { TestApp } from '@baserow/test/helpers/testApp'
import RowHistoryFieldLinkRow from '@baserow/modules/database/components/row/RowHistoryFieldLinkRow'

describe('RowHistoryFieldLinkRow', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(() => {
    testApp.afterEach()
  })

  const mountComponent = (entry) => {
    return testApp.mount(RowHistoryFieldLinkRow, {
      propsData: {
        entry,
        fieldIdentifier: 'field_1',
      },
    })
  }

  const buildEntry = (linkedRows) => ({
    before: { field_1: [] },
    after: { field_1: Object.keys(linkedRows).map((id) => Number(id)) },
    fields_metadata: {
      field_1: {
        linked_rows: linkedRows,
      },
    },
  })

  test('renders the primary value when present', async () => {
    const wrapper = await mountComponent(
      buildEntry({
        42: { value: 'Hello world' },
      })
    )
    expect(wrapper.text()).toContain('Hello world')
  })

  test('falls back to the unnamed-row label when value is empty', async () => {
    const wrapper = await mountComponent(
      buildEntry({
        42: { value: '' },
      })
    )
    // The repo-wide i18n mock returns the key unchanged, so we assert on the
    // key path rather than on the rendered English string.
    expect(wrapper.text()).toContain('functionnalGridViewFieldLinkRow.unnamed')
  })

  test('falls back when the linked row metadata is missing entirely', async () => {
    // The diff references row 42 but the metadata dict has no entry for it.
    const entry = {
      before: { field_1: [] },
      after: { field_1: [42] },
      fields_metadata: { field_1: { linked_rows: {} } },
    }
    const wrapper = await mountComponent(entry)
    expect(wrapper.text()).toContain('functionnalGridViewFieldLinkRow.unnamed')
  })
})
