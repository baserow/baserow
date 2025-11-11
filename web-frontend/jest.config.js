const coverageConfig = require('./coverage.config.js')
const path = require('path')

module.exports = {
  testEnvironment: 'jsdom',
  testMatch: ['<rootDir>/test/unit/**/*.spec.js'],
  moduleFileExtensions: ['js', 'json', 'vue', '.mjs'],
  moduleNameMapper: {
    '^@baserow/(.*).(scss|sass)$': '<rootDir>/test/helpers/scss.js',
    '^@baserow/(.*)$': '<rootDir>/$1',
    '^@baserow_test_cases/(.*)$': path.join(__dirname, '../tests/cases/$1'),
    '^@/(.*)$': '<rootDir>/$1',
    '^~/(.*)$': '<rootDir>/$1',
    '^vue$': '<rootDir>/node_modules/vue/dist/vue.common.js',
  },
  transform: {
    '^.+\\.(mjs|js)$': 'babel-jest',
    '^.+\\.vue$': '@vue/vue2-jest',
    '^.+\\.(gif|ico|jpg|jpeg|png|svg)$':
      '<rootDir>/test/helpers/stubFileTransformer.js',
  },
  transformIgnorePatterns: ['/node_modules/(?!@nuxtjs/composition-api)'],
  setupFilesAfterEnv: ['<rootDir>/jest.setup.js'],
  snapshotSerializers: ['<rootDir>/node_modules/jest-serializer-vue'],
  cacheDirectory: '<rootDir>/.cache/jest',
  ...coverageConfig,
}
