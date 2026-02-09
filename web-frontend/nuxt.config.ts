const isTest = process.env.VITEST || process.env.APP_ENV === 'test'
const isDev = process.env.APP_ENV === 'dev'

export default isTest
  ? (await import('./config/nuxt.config.test.ts')).default
  : isDev
    ? (await import('./config/nuxt.config.dev.ts')).default
    : (await import('./config/nuxt.config.prod.ts')).default
