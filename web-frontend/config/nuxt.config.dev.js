import StyleLintPlugin from 'stylelint-webpack-plugin'

import base from './nuxt.config.base.js'

export default Object.assign(base(), {
  vue: {
    config: {
      productionTip: false,
      devtools: true,
      performance: true,
      silent: false,
    },
  },
  dev: true,
  build: {
    extend(config, ctx) {
      config.node = { fs: 'empty' }
      if (ctx.isDev) {
        config.devtool = ctx.isClient ? 'source-map' : 'inline-source-map'
      }
    },
    babel: { compact: true },
    plugins: [
      new StyleLintPlugin({
        syntax: 'scss',
      }),
    ],
    transpile: ['axios'],
  },
})
