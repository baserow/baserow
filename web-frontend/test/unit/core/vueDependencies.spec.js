import { realpathSync } from 'node:fs'
import { createRequire } from 'node:module'

const require = createRequire(import.meta.url)

const resolveFrom = (entrypoint, dependency) => {
  // nuxt only exports an `import` condition, so require.resolve can't find it.
  const entrypointRequire = createRequire(import.meta.resolve(entrypoint))
  return realpathSync(entrypointRequire.resolve(dependency))
}

describe('Vue dependencies', () => {
  test('@vue/compiler-core uses the root entities decoder', () => {
    expect(resolveFrom('@vue/compiler-core', 'entities/decode')).toBe(
      realpathSync(require.resolve('entities/decode'))
    )
  })

  test.each([
    'nuxt',
    '@nuxt/nitro-server',
    '@nuxt/test-utils',
    '@nuxt/vite-builder',
    '@unhead/vue',
    '@vitejs/plugin-vue',
    '@vitejs/plugin-vue-jsx',
    '@vue/devtools-core',
    'vite-plugin-vue-tracer',
  ])('%s uses the root Vue runtime', (entrypoint) => {
    expect(resolveFrom(entrypoint, 'vue')).toBe(
      realpathSync(require.resolve('vue'))
    )
  })
})
