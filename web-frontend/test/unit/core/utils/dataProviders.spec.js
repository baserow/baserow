import { DataProviderType } from '@baserow/modules/core/dataProviderTypes'
import { getSampleValueFromDataProviders } from '@baserow/modules/core/utils/dataProviders'

class WithSamplesDataProviderType extends DataProviderType {
  static getType() {
    return 'with_samples'
  }

  getSampleValue(applicationContext, path) {
    return { applicationContext, path }
  }
}

class WithoutSamplesDataProviderType extends DataProviderType {
  static getType() {
    return 'without_samples'
  }
}

describe('getSampleValueFromDataProviders', () => {
  const dataProviders = [
    new WithSamplesDataProviderType({ app: {} }),
    new WithoutSamplesDataProviderType({ app: {} }),
  ]
  const applicationContext = { page: { id: 1 } }

  test('asks the data provider the path belongs to', () => {
    expect(
      getSampleValueFromDataProviders(
        dataProviders,
        applicationContext,
        'with_samples.12.0.field_34'
      )
    ).toStrictEqual({ applicationContext, path: ['12', '0', 'field_34'] })
  })

  test('has no value for a data provider without sample values', () => {
    expect(
      getSampleValueFromDataProviders(
        dataProviders,
        applicationContext,
        'without_samples.12.name'
      )
    ).toBeUndefined()
  })

  test('has no value for a data provider that is not offered', () => {
    expect(
      getSampleValueFromDataProviders(
        dataProviders,
        applicationContext,
        'unknown.12.name'
      )
    ).toBeUndefined()
    expect(
      getSampleValueFromDataProviders(undefined, applicationContext, 'a.b')
    ).toBeUndefined()
  })
})
