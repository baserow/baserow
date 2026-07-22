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

/**
 * Work around development-only warnings in the currently installed Nuxt and
 * dependency releases. Keep these fixes local to the exact affected files so
 * source maps remain enabled for Baserow code and all unaffected dependencies.
 */
export const viteDevelopmentCompatibility = {
  name: 'baserow:development-dependency-compatibility',
  apply: 'serve',
  enforce: 'pre',
  async load(id) {
    const filePath = id.split('?', 1)[0]
    const normalizedPath = filePath.replaceAll('\\', '/')

    if (normalizedPath.endsWith(NUXT_PAGE_CHECK_PLUGIN)) {
      const code = await readFile(filePath, 'utf8')

      // Nuxt 4.5's plugin analyzer does not recognize `plugin as default` in a
      // named export list, so its own valid plugin is reported and discarded.
      // Writing the equivalent explicit default export lets it be analyzed.
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

    // entities@4 publishes maps whose sourceRoot escapes its package,
    // https-proxy-agent omits the referenced TypeScript source, and
    // moment-guess publishes a map reference without publishing the map file.
    // Loading only these files without the invalid comments avoids Vite trying
    // to resolve data which does not exist and cannot aid local debugging.
    const code = await readFile(filePath, 'utf8')
    return {
      code: code.replace(sourceMapComment, ''),
      map: null,
    }
  },
}
