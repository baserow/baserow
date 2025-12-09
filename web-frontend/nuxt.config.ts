const isTest = process.env.VITEST

export default isTest
  ? (await import('./config/nuxt.config.test.ts')).default
  : (await import('./config/nuxt.config.prod.ts')).default
