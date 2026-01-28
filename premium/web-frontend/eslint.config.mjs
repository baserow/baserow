// @ts-check
import withNuxt from '../../web-frontend/.nuxt/eslint.config.mjs'
import common from '../../web-frontend/eslint.config.common.mjs'

export default withNuxt([
  ...common,
  { rules: { 'vue/order-in-components': 'off' } },
])
