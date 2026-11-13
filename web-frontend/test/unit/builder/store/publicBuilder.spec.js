import { vi } from 'vitest'
import publicBuilderStore from '@baserow/modules/builder/store/publicBuilder'

vi.mock('@baserow/modules/builder/services/publishedBuilder', () => ({
  fetchPublicBuilder: vi.fn(() => Promise.resolve({ id: 1 })),
}))

async function fetch(params) {
  const state = publicBuilderStore.state()
  const commit = (type, value) =>
    publicBuilderStore.mutations[type](state, value)
  const dispatch = vi.fn(() => Promise.resolve({ id: 1 }))
  await publicBuilderStore.actions.fetch.call(
    { $client: {} },
    { commit, dispatch },
    params
  )
  return publicBuilderStore.getters.getPublicDomain(state)
}

describe('publicBuilder store', () => {
  test('remembers the domain a published builder is loaded from', async () => {
    expect(await fetch({ domain: 'app.example.com' })).toBe('app.example.com')
  })

  test('has no public domain for a builder loaded by id', async () => {
    expect(await fetch({ builderId: 1, domain: 'baserow.example.com' })).toBe(
      null
    )
  })

  test('has no public domain in preview mode', async () => {
    expect(
      await fetch({
        mode: 'preview',
        builderId: 1,
        domain: 'preview.example.com',
      })
    ).toBe(null)
  })
})
