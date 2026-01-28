// Please keep in sync with the premium/enterprise eslintrc.js
import withNuxt from './.nuxt/eslint.config.mjs'

import globals from 'globals'
import vitest from 'eslint-plugin-vitest'
import prettier from 'eslint-config-prettier'

export default [
  {
    ignores: [
      '.nuxt/**',
      '**/node_modules/**',
      'coverage/**',
      '**/generated/**',
      '.nuxt-storybook/**',
    ],
  },
  prettier,
  {
    languageOptions: {
      globals: {
        ...globals.browser,
        ...globals.node,
      },
    },
    rules: {
      'no-console': 0,
      'vue/no-mutating-props': 0,
      'import/order': 'off',
      'vue/html-self-closing': 'off',
      'vue/no-unused-components': 'warn',
      'vue/no-use-computed-property-like-method': 'off',
      'vue/multi-word-component-names': 'off',
      'vue/no-reserved-component-names': 'off',
      'import/no-named-as-default-member': 'off',
      'no-unused-vars': 'off',
      '@typescript-eslint/no-unused-vars': 'off',
      '@typescript-eslint/no-explicit-any': 'off',
      '@typescript-eslint/no-dynamic-delete': 'off',
      'no-empty': 'off',
    },
  },

  {
    files: [
      '**/*.{test,spec}.{js,ts,jsx,tsx}',
      '**/__tests__/**/*.{js,ts,jsx,tsx}',
    ],
    plugins: { vitest },
    languageOptions: {
      globals: {
        ...vitest.environments.env.globals,
      },
    },
    rules: {
      ...vitest.configs.recommended.rules,
    },
  },
]
