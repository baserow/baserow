import { readFile } from 'node:fs/promises'

const NUXT_PAGE_CHECK_PLUGIN =
  '/node_modules/nuxt/dist/pages/runtime/plugins/check-if-page-unused.js'
const NUXT_PAGE_CHECK_NAMED_EXPORT =
  'export { NESTED_PAGE_CONFIRMATION_DELAY, plugin as default, findUnrenderedNestedPage };'
const NUXT_PAGE_CHECK_DEFAULT_EXPORT =
  'export default plugin;\nexport { NESTED_PAGE_CONFIRMATION_DELAY, findUnrenderedNestedPage };'

const BROKEN_SOURCE_MAP_PATHS = [
  '/node_modules/https-proxy-agent/dist/index.js',
  '/node_modules/markdown-it/node_modules/entities/lib/esm/',
  '/node_modules/moment-guess/dist/bundle.esm.js',
]

const sourceMapComment = /^\s*\/\/# sourceMappingURL=.*$/gm

export const viteDevelopmentCompatibility = {
  name: 'baserow:development-dependency-compatibility',
  apply: 'serve',
  enforce: 'pre',
  async load(id) {
    const filePath = id.split('?', 1)[0]
    const normalizedPath = filePath.replaceAll('\\', '/')

    if (normalizedPath.endsWith(NUXT_PAGE_CHECK_PLUGIN)) {
      const code = await readFile(filePath, 'utf8')

      // Nuxt's analyzer misses the equivalent named default export.
      return code.replace(
        NUXT_PAGE_CHECK_NAMED_EXPORT,
        NUXT_PAGE_CHECK_DEFAULT_EXPORT
      )
    }

    if (
      !normalizedPath.endsWith('.js') ||
      !BROKEN_SOURCE_MAP_PATHS.some((dependencyPath) =>
        normalizedPath.includes(dependencyPath)
      )
    ) {
      return null
    }

    // These packages reference source-map files or sources they do not publish.
    const code = await readFile(filePath, 'utf8')
    return {
      code: code.replace(sourceMapComment, ''),
      map: null,
    }
  },
}
