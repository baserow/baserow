export default function (
  base = '@',
  premiumBase = '@/../premium/web-frontend',
  enterpriseBase = '@/../enterprise/web-frontend'
) {
  // Support adding in extra modules say from a plugin using the ADDITIONAL_MODULES
  // env variable which is a comma separated list of absolute module paths.
  const additionalModulesCsv = process.env.ADDITIONAL_MODULES
  const additionalModules = additionalModulesCsv
    ? additionalModulesCsv
        .split(',')
        .map((m) => m.trim())
        .filter((m) => m !== '')
    : []

  if (additionalModules.length > 0) {
    console.log(`Loading extra plugin modules: ${additionalModules}`)
  }
  const baseModules = [
    base + '/modules/core/module.js',
    base + '/modules/database/module.js',
    base + '/modules/integrations/module.js',
    base + '/modules/builder/module.js',
    base + '/modules/dashboard/module.js',
    base + '/modules/automation/module.js',
  ]
  if (!process.env.BASEROW_OSS_ONLY) {
    baseModules.push(
      premiumBase + '/modules/baserow_premium/module.js',
      enterpriseBase + '/modules/baserow_enterprise/module.js'
    )
  }
  baseModules.push('@nuxtjs/sentry')

  const modules = baseModules.concat(additionalModules)
  return {
    modules,
    buildModules: [
      '@nuxtjs/stylelint-module',
      '@nuxtjs/svg',
      '@nuxtjs/composition-api/module',
    ],
    sentry: {
      clientIntegrations: {
        Dedupe: {},
        ExtraErrorData: {},
        RewriteFrames: {},
        ReportingObserver: null,
      },
      clientConfig: {
        attachProps: true,
        logErrors: true,
      },
    },
    build: {
      extend(config, ctx) {
        config.node = { fs: 'empty' }
        config.module.rules.push({
          test: /\.(m|c)js$/,
          include: /node_modules/,
          type: 'javascript/auto',
        })
      },
      babel: { compact: true },
      transpile: [
        'axios',
        'tiptap-markdown',
        'markdown-it',
        'vue-chartjs',
        'chart.js',
        // Transpiler tous les modules d3 correctement
        'd3',
        'd3-zoom',
        'd3-dispatch',
        'd3-selection',
        'd3-drag',
        'd3-interpolate',
        'd3-transition',
        'd3-ease',
        'd3-hierarchy',
        'd3-force',
        'd3-shape',
        'd3-scale',
        'd3-axis',
        'd3-brush',
        'd3-color',
        'd3-format',
        'd3-time',
        'd3-time-format',
        'd3-timer',
        'd3-interpolate-path',
        'd3-interpolate-string',
        'd3-interpolate-transform',
      ],
    },
  }
}
