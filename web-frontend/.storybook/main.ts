import type { StorybookConfig } from '@nuxtjs/storybook'
import { mergeConfig } from 'vite'

const config: StorybookConfig = {
  stories: [
    '../stories/**/*.mdx',
    '../stories/**/*.stories.@(js|jsx|mjs|ts|tsx)',
  ],
  addons: [
    '@storybook/addon-links',
    '@storybook/addon-docs',
    '@storybook/addon-designs',
  ],
  framework: {
    name: '@storybook-vue/nuxt',
    options: {
      // vue-docgen-api tries to read Nuxt's virtual page modules from disk.
      // vue-component-meta skips those virtual modules and still documents real components.
      docgen: 'vue-component-meta',
    },
  },
  docs: {
    autodocs: 'tag',
  },
  /** Limit 504 "Outdated Optimize Dep" on cold start: wait for dep crawl, pre-bundle common deps. */
  async viteFinal(viteConfig) {
    return mergeConfig(viteConfig, {
      optimizeDeps: {
        holdUntilCrawlEnd: true,
        include: [
          'axios',
          'lodash',
          'lodash-es',
          'mitt',
          'papaparse',
          'posthog-js',
          'flush-promises',
          'vuex',
          'moment',
        ],
      },
    })
  },
}
export default config
