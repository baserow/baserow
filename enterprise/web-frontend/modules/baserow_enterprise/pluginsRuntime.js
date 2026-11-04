import { BaserowPlugin } from '@baserow/modules/core/plugins'

/** Enterprise behavior required by published and preview Builder pages. */
export class EnterpriseRuntimePlugin extends BaserowPlugin {
  static getType() {
    return 'enterprise'
  }

  /**
   * Adds the custom CSS/JS defined for this builder.
   */
  getBuilderApplicationHeaderAddition({ builder, mode }) {
    if (builder.untrusted_content) {
      return { link: [], script: [] }
    }

    const customCodeBase =
      mode === 'preview'
        ? `${this.app.$config.public.publicBackendUrl}/api/builder/preview/${builder.id}/custom-code`
        : `${this.app.$config.public.publicBackendUrl}/api/custom_code/${builder.id}`
    const css = `${customCodeBase}/css/${mode === 'preview' ? '' : 'public/'}`
    const js = `${customCodeBase}/js/${mode === 'preview' ? '' : 'public/'}`

    const script = []
    const link = []

    builder.scripts.forEach((s) => {
      if (!s.url) {
        return
      }

      const crossorigin =
        s.crossorigin === 'credentials'
          ? 'use-credentials'
          : s.crossorigin === 'anonymous'
            ? 'anonymous'
            : null

      if (s.type === 'javascript') {
        script.push({
          src: s.url,
          crossorigin,
          defer: s.load_type === 'defer',
          async: s.load_type === 'async',
          tagPosition: 'bodyClose',
        })
      }

      if (s.type === 'stylesheet') {
        script.push({
          rel: 'stylesheet',
          href: s.url,
          crossorigin,
          tagPosition: 'bodyClose',
        })
      }
    })

    if (builder.custom_code.css) {
      link.push({
        rel: 'stylesheet',
        href: css,
        crossorigin: mode === 'preview' ? 'use-credentials' : null,
        tagPosition: 'bodyClose',
      })
    }
    if (builder.custom_code.js) {
      script.push({
        src: js,
        crossorigin: mode === 'preview' ? 'use-credentials' : null,
        defer: true,
        tagPosition: 'bodyClose',
      })
    }

    return {
      link,
      script,
    }
  }
}
