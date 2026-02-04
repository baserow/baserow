import baseConfig from '../../web-frontend/vitest.config.base'
import { defineVitestConfig } from '@nuxt/test-utils/config'

export default defineVitestConfig({
  test: {
    ...baseConfig.test,
    setupFiles: ['../web-frontend/vitest.setup.ts'],
    include: ['../enterprise/web-frontend/test/**/*.{test,spec}.{js,ts}'],
  },
})
