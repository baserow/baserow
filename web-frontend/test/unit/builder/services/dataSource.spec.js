import { describe, expect, test, vi } from 'vitest'

import DataSourceService from '@baserow/modules/builder/services/dataSource'

describe('data source service', () => {
  test('uses the preview-scoped endpoint when resolving preview record names', async () => {
    const client = {
      get: vi.fn().mockResolvedValue({ data: { 42: 'Ada' } }),
    }

    const recordNames = await DataSourceService(client).getRecordNames(
      5,
      [42],
      'preview',
      3
    )

    expect(client.get).toHaveBeenCalledWith(
      'builder/preview/3/data-sources/5/record-names/',
      { params: { record_ids: '42' } }
    )
    expect(recordNames).toStrictEqual({ 42: 'Ada' })
  })

  test('uses the published endpoint when resolving public record names', async () => {
    const client = {
      get: vi.fn().mockResolvedValue({ data: { 42: 'Ada' } }),
    }

    const recordNames = await DataSourceService(client).getRecordNames(
      5,
      [42],
      'public',
      3
    )

    expect(client.get).toHaveBeenCalledWith(
      'builder/domains/published/data-source/5/record-names/',
      { params: { record_ids: '42' } }
    )
    expect(recordNames).toStrictEqual({ 42: 'Ada' })
  })

  test('uses the generic endpoint while editing', async () => {
    const client = {
      get: vi.fn().mockResolvedValue({ data: { 42: 'Ada' } }),
    }

    const recordNames = await DataSourceService(client).getRecordNames(
      5,
      [42],
      'editing',
      3
    )

    expect(client.get).toHaveBeenCalledWith(
      'builder/data-source/5/record-names/',
      { params: { record_ids: '42' } }
    )
    expect(recordNames).toStrictEqual({ 42: 'Ada' })
  })
})
