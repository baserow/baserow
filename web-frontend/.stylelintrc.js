module.exports = {
  overrides: [
    {
      files: ['**/*.scss'],
      customSyntax: 'postcss-scss',
    },
  ],
  extends: ['stylelint-config-standard-scss'],
  plugins: ['stylelint-selector-bem-pattern'],
  rules: {
    'selector-class-pattern': [
      '^[a-z]([-]?[a-z0-9]+)*(__[a-z0-9]([-]?[a-z0-9]+)*)?(--[a-z0-9]([-]?[a-z0-9]+)*)?$',
      {
        resolveNestedSelectors: true,
        message: function expected(selectorValue) {
          return `Expected class selector "${selectorValue}" to match BEM CSS pattern https://en.bem.info/methodology/css. Selector validation tool: https://regexr.com/3apms`
        },
      },
    ],
    'plugin/selector-bem-pattern': {
      componentName: '[A-Z]+',
      componentSelectors: {
        initial: '^\\.{componentName}(?:-[a-z]+)?$',
        combined: '^\\.combined-{componentName}-[a-z]+$',
      },
      utilitySelectors: '^\\.util-[a-z]+$',
    },
    'scss/dollar-variable-pattern': null,
    'scss/dollar-variable-empty-line-before': null,
    'at-rule-no-unknown': [
      true,
      {
        ignoreAtRules: [
          '/regex/',
          'function',
          'if',
          'each',
          'else',
          'include',
          'mixin',
          'return',
          'extend',
          'for',
          'use',
          'forward',
        ],
      },
    ],
    'media-feature-range-notation': 'prefix',
    'color-function-notation': 'legacy',
    'scss/no-global-function-names': null,
    'alpha-value-notation': 'number',
    'selector-not-notation': 'simple',
  },
}
