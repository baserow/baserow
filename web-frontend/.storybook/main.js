const { nuxifyStorybook } = require('../.nuxt-storybook/storybook/main.js')

module.exports = nuxifyStorybook({
  webpackFinal(config, { configDir }) {
    config.node = { fs: 'empty' }
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
