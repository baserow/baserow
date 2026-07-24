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
      // The Nuxt bridge exposes virtual Vue modules that docgen cannot read.
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
