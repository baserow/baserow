import { expect, test } from 'vitest'
import { createApplicationFeatureBundles } from '@baserow/config/applicationFeatureBundles'

test('groups exclusive feature code while keeping startup metadata and cross-application helpers shared', () => {
  const graph = {
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
