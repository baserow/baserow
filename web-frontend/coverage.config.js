const path = require('path')

// Setting reporters on the command line does not work so enable via this env variable
// we have to set anyway when using the junit reporter in CI.
const junitReporterConfig = process.env.JEST_JUNIT_OUTPUT_DIR
  ? {
      reporters: ['default', path.join(__dirname, '/node_modules/jest-junit')],
    }
  : {}

module.exports = {
  coverageReporters: [
    'text-summary',
    ['cobertura', { projectRoot: '/baserow/' }],
  ],
  collectCoverageFrom: [
    '<rootDir>/modules/**/*.{js,Vue,vue}',
    '!**/node_modules/**',
    '!**/.nuxt/**',
    '!**/reports/**',
    '!**/test/**',
    '!**/generated/**',
    '!**/iconoir.js',
  ],
  ...junitReporterConfig,
}
