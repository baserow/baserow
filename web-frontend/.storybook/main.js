const { nuxifyStorybook } = require('../.nuxt-storybook/storybook/main.js')

module.exports = nuxifyStorybook({
  webpackFinal(config, { configDir }) {
    config.node = { fs: 'empty' }
    config.resolve = {
      ...config.resolve,
      alias: {
        ...config.resolve.alias,
        '@vueuse/core': require.resolve('@vueuse/core'),
      },
    }
    return config
  },
  features: { buildStoriesJson: true },
  stories: ['../stories/*.stories.mdx'],
  addons: [
    'storybook-addon-pseudo-states',
    'storybook-addon-designs',
    '@storybook/addon-coverage',
  ],
})
