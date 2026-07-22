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
      // Nuxt layouts are exposed to Storybook as virtual Vue files. The
      // Storybook 9 docgen plugin used by the current Nuxt bridge tries to read
      // those virtual IDs from disk and makes Storybook 10 builds fail.
      docgen: false,
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
