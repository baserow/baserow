import { realpathSync } from 'node:fs'
import { createRequire } from 'node:module'

const require = createRequire(import.meta.url)

const resolveFrom = (entrypoint, dependency) => {
  const entrypointRequire = createRequire(require.resolve(entrypoint))
  return realpathSync(entrypointRequire.resolve(dependency))
}

describe('Vue dependencies', () => {
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
