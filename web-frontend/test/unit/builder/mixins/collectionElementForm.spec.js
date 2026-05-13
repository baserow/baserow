import collectionElementForm from '@baserow/modules/builder/mixins/collectionElementForm'

vi.mock('@baserow/modules/builder/dataProviderTypes', () => ({
  UserDataProviderType: {
    getType: () => 'user',
  },
  CurrentRecordDataProviderType: {
    getType: () => 'current_record',
  },
  PageParameterDataProviderType: {
    getType: () => 'page_parameter',
  },
  DataSourceDataProviderType: {
    getType: () => 'data_source',
  },
  DataSourceContextDataProviderType: {
    getType: () => 'data_source_context',
  },
  FormDataProviderType: {
    getType: () => 'form_data',
  },
  PreviousActionDataProviderType: {
    getType: () => 'previous_action',
  },
}))

describe('collectionElementForm', () => {
  test.each([
    [true, true],
    [false, false],
  ])(
    'pagingOptionsAvailable follows selectedDataSourceSupportsPagination=%s',
    (selectedDataSourceSupportsPagination, expected) => {
      expect(
        collectionElementForm.computed.pagingOptionsAvailable.call({
          selectedDataSourceSupportsPagination,
        })
      ).toBe(expected)
    }
  )

  test('selectedDataSourceSupportsPagination is true only when the service type supports it', () => {
    expect(
      collectionElementForm.computed.selectedDataSourceSupportsPagination.call({
        selectedDataSourceType: { supportsPagination: true },
      })
    ).toBe(true)
    expect(
      collectionElementForm.computed.selectedDataSourceSupportsPagination.call({
        selectedDataSourceType: { supportsPagination: false },
      })
    ).toBe(false)
    expect(
      collectionElementForm.computed.selectedDataSourceSupportsPagination.call({
        selectedDataSourceType: null,
      })
    ).toBe(false)
  })
})
