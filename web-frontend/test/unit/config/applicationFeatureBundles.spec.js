import { expect, test } from 'vitest'
import { createApplicationFeatureBundles } from '@baserow/config/applicationFeatureBundles'

test('groups exclusive feature code while keeping startup metadata and cross-application helpers shared', () => {
  const graph = {
    '/modules/core/pages/onboarding.vue': ['/route-progress'],
    '/modules/core/onboardingBundle.js': [
      '/modules/core/components/onboarding/MoreStep.vue',
    ],
    '/modules/database/onboardingBundle.js': ['/onboarding-form'],
    '/modules/database/onboardingRenderingBundle.js': ['/onboarding-preview'],
    '/modules/database/applicationBundle.js': [
      '/database-ui',
      '/shared',
      '/database-metadata',
    ],
    '/modules/dashboard/applicationBundle.js': ['/dashboard-ui', '/shared'],
    '/modules/database/pluginMetadata.js': ['/database-metadata'],
    '/database-ui': ['/database-cycle'],
    '/database-cycle': ['/database-ui'],
    '/modules/baserow_premium/databaseBundle.js': ['/premium-database-ui'],
  }
  const { plugin, groups } = createApplicationFeatureBundles()
  plugin.buildEnd.call({
    getModuleIds: () => Object.keys(graph),
    getModuleInfo: (id) => ({ importedIds: graph[id] || [] }),
  })
  const assignedTo = (id) =>
    groups.filter((group) => group.test(id)).map((group) => group.name)
  expect(
    assignedTo('/modules/core/components/onboarding/MoreStep.vue')
  ).toEqual(['onboarding'])
  expect(assignedTo('/modules/core/pages/onboarding.vue')).toEqual([])
  expect(assignedTo('/route-progress')).toEqual([])
  expect(assignedTo('/onboarding-form')).toEqual(['onboarding'])
  expect(assignedTo('/onboarding-preview')).toEqual(['onboarding-rendering'])
  expect(assignedTo('/database-ui')).toEqual(['database-application'])
  expect(assignedTo('/database-cycle')).toEqual(['database-application'])
  expect(assignedTo('/premium-database-ui')).toEqual(['database-application'])
  expect(assignedTo('/dashboard-ui')).toEqual(['dashboard-application'])
  expect(assignedTo('/shared')).toEqual(['application-shared'])
  expect(assignedTo('/database-metadata')).toEqual([])
  expect(assignedTo('/unused-dynamic-feature')).toEqual([])
})

test('the production bundler leaves application UI out of the metadata import graph', async () => {
  const { rolldown } = await import('rolldown')
  const modules = {
    '/entry.js': `import { label } from '/modules/database/pluginMetadata.js'; console.log(label); export const open = () => import('/modules/database/applicationBundle.js'); export const openDashboard = () => import('/modules/dashboard/applicationBundle.js')`,
    '/modules/database/pluginMetadata.js': `export { label } from '/database-metadata.js'`,
    '/database-metadata.js': `export const label = 'Database'`,
    '/modules/database/applicationBundle.js': `export { label } from '/database-metadata.js'; export { render } from '/database-ui.js'; export { shared } from '/shared-feature-ui.js'`,
    '/database-ui.js': `export function render() { return 'Grid' }`,
    '/modules/dashboard/applicationBundle.js': `export { shared } from '/shared-feature-ui.js'`,
    '/shared-feature-ui.js': `export const shared = 'Editor controls'`,
  }
  const features = createApplicationFeatureBundles()
  const bundle = await rolldown({
    input: '/entry.js',
    plugins: [
      {
        name: 'application-test-modules',
        resolveId: (id) => (id in modules ? id : null),
        load: (id) => modules[id],
      },
      features.plugin,
    ],
  })
  try {
    const { output } = await bundle.generate({
      format: 'esm',
      codeSplitting: { groups: features.groups },
    })
    const chunks = output.filter((file) => file.type === 'chunk')
    const initialModules = new Set()
    const visit = (chunk) => {
      for (const id of Object.keys(chunk.modules)) initialModules.add(id)
      for (const dependency of chunk.imports)
        visit(chunks.find((file) => file.fileName === dependency))
    }
    visit(chunks.find((chunk) => chunk.isEntry))
    expect(initialModules.has('/database-metadata.js')).toBe(true)
    expect(initialModules.has('/database-ui.js')).toBe(false)
    expect(initialModules.has('/shared-feature-ui.js')).toBe(false)
    expect(
      chunks.find((chunk) => '/shared-feature-ui.js' in chunk.modules).name
    ).toBe('application-shared')
    expect(
      chunks.find((chunk) => '/database-ui.js' in chunk.modules).name
    ).toBe('database-application')
  } finally {
    await bundle.close()
  }
})

test('initial onboarding does not fetch Database through shared preview metadata', async () => {
  const { rolldown } = await import('rolldown')
  const modules = {
    '/entry.js': `export const start = () => import('/modules/core/onboardingBundle.js'); export const database = () => import('/modules/database/applicationBundle.js')`,
    '/modules/core/onboardingBundle.js': `export { exclusive } from '/onboarding-form.js'; export { form } from '/onboarding-metadata.js'; export const preview = () => import('/modules/database/onboardingRenderingBundle.js')`,
    '/onboarding-metadata.js': `export const form = 'Database name'`,
    '/onboarding-form.js': `export const exclusive = 'Onboarding form'`,
    '/modules/database/onboardingRenderingBundle.js': `export { form } from '/onboarding-metadata.js'; export { grid } from '/database-editor.js'`,
    '/modules/database/applicationBundle.js': `export { grid } from '/database-editor.js'; export { form } from '/onboarding-metadata.js'`,
    '/database-editor.js': `export const grid = 'Full Grid editor'`,
  }
  const features = createApplicationFeatureBundles()
  const bundle = await rolldown({
    input: '/entry.js',
    plugins: [
      {
        name: 'onboarding-test-modules',
        resolveId: (id) => (id in modules ? id : null),
        load: (id) => modules[id],
      },
      features.plugin,
    ],
  })
  try {
    const { output } = await bundle.generate({
      format: 'esm',
      codeSplitting: { groups: features.groups },
    })
    const chunks = output.filter((file) => file.type === 'chunk')
    const loaded = new Set()
    const visit = (chunk) => {
      for (const id of Object.keys(chunk.modules)) loaded.add(id)
      for (const dependency of chunk.imports)
        visit(chunks.find((file) => file.fileName === dependency))
    }
    visit(
      chunks.find(
        (chunk) => '/modules/core/onboardingBundle.js' in chunk.modules
      )
    )
    expect(loaded.has('/onboarding-metadata.js')).toBe(true)
    expect(loaded.has('/database-editor.js')).toBe(false)
    loaded.clear()
    visit(
      chunks.find(
        (chunk) => '/modules/database/applicationBundle.js' in chunk.modules
      )
    )
    expect(loaded.has('/onboarding-form.js')).toBe(false)
  } finally {
    await bundle.close()
  }
})
