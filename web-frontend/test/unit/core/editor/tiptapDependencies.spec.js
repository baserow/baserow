import { realpathSync } from 'node:fs'
import { createRequire } from 'node:module'

const require = createRequire(import.meta.url)

const resolveFrom = (entrypoint, dependency) => {
  const entrypointRequire = createRequire(require.resolve(entrypoint))
  return realpathSync(entrypointRequire.resolve(dependency))
}

describe('TipTap dependencies', () => {
  test.each([
    ['@tiptap/pm/model', 'prosemirror-model'],
    ['@tiptap/pm/transform', 'prosemirror-transform'],
    ['@tiptap/pm/view', 'prosemirror-view'],
  ])('%s uses the root %s instance', (entrypoint, dependency) => {
    expect(resolveFrom(entrypoint, dependency)).toBe(
      realpathSync(require.resolve(dependency))
    )
  })

  test('prosemirror-transform uses the root prosemirror-model instance', () => {
    const rootModel = realpathSync(require.resolve('prosemirror-model'))
    const tiptapTransform = resolveFrom(
      '@tiptap/pm/transform',
      'prosemirror-transform'
    )
    const transformModel = resolveFrom(tiptapTransform, 'prosemirror-model')

    expect(transformModel).toBe(rootModel)
  })
})
