import base from './nuxt.config.base.js'

const baseConfig = base()
export default {
  ...baseConfig,
  ...{
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
      cache: true,
      hardSource: true,
      sourceMap: true,
      parallel: true,
      quite: true,
      optimization: {
        splitChunks: {
          chunks: 'async',
        },
      },
      ...baseConfig.build,
      ...{
        extend(config, ctx) {
          baseConfig.build.extend(config, ctx)
          if (ctx.isDev) {
            config.devtool = ctx.isClient ? 'source-map' : 'inline-source-map'
          }
        },
      },
    },
  },
}
