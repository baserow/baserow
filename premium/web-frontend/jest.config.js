const path = require('path')

module.exports = {
  displayName: 'premium-unit',
  testEnvironment: 'jsdom',
  testMatch: ['<rootDir>/test/unit/**/*.spec.js'],
  moduleFileExtensions: ['js', 'json', 'vue', '.mjs'],
  moduleDirectories: [
    path.join(__dirname, '/../../web-frontend/node_modules/'),
  ],
  modulePaths: [path.join(__dirname, '/../../web-frontend/node_modules/')],
  moduleNameMapper: {
    '^@baserow/(.*).(scss|sass)$': path.join(
      __dirname,
      '/../../web-frontend/test/helpers/scss.js'
    ),
    '^@baserow/(.*)$': path.join(__dirname, '/../../web-frontend/$1'),
    '^@baserow_premium/(.*)$': path.join(
      __dirname,
      '/../../premium/web-frontend/modules/baserow_premium/$1'
    ),
    '^@baserow_premium_test/(.*)$': path.join(
      __dirname,
      '/../../premium/web-frontend/test/$1'
    ),
    '^@/(.*)$': path.join(__dirname, '/../../web-frontend/$1'),
    '^~/(.*)$': path.join(__dirname, '/../../web-frontend/$1'),
    '^vue$': path.join(
      __dirname,
      '/../../web-frontend/node_modules/vue/dist/vue.common.js'
    ),
  },
  transform: {
    '^.+\\.(mjs|js)$': [
      'babel-jest',
      {
        configFile: path.join(__dirname, '/../../web-frontend/babel.config.js'),
      },
    ],
    '^.+\\.vue$': '../../web-frontend/node_modules/@vue/vue2-jest',
    '^.+\\.(gif|ico|jpg|jpeg|png|svg)$':
      '../../web-frontend/test/helpers/stubFileTransformer.js',
  },
  transformIgnorePatterns: ['/node_modules/(?!@nuxtjs/composition-api)'],
  setupFilesAfterEnv: [
    path.join(__dirname, '/../../premium/web-frontend/jest.setup.js'),
  ],
  snapshotSerializers: [
    path.join(
      __dirname,
      '/../../web-frontend/node_modules/jest-serializer-vue'
    ),
  ],
  coverageReporters: [
    'text-summary',
    ['cobertura', { projectRoot: '/baserow/' }],
  ],
  collectCoverageFrom: [
    '**/*.{js,Vue,vue}',
    '!**/node_modules/**',
    '!**/.nuxt/**',
    '!**/reports/**',
    '!**/test/**',
    '!**/generated/**',
  ],
}
