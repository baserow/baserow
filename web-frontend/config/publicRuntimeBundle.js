/**
 * Consolidate the public page's static dependency graph so feature boundaries
 * do not turn startup into many requests for shared runtime helpers. Dynamic
 * imports stay outside this group, including authoring UI and optional charts.
 */
export function createPublicRuntimeBundle() {
  const runtimeModules = new Set()
  return {
    plugin: {
      name: 'baserow-public-runtime-bundle',
      buildEnd(error) {
        if (error) return
        const visit = (id) => {
          if (runtimeModules.has(id)) return
          runtimeModules.add(id)
          for (const dependency of this.getModuleInfo(id)?.importedIds || []) {
            visit(dependency)
          }
        }
        for (const id of this.getModuleIds()) {
          if (
            this.getModuleInfo(id)?.isEntry ||
            id.includes('/modules/builder/pages/publicPage.vue')
          ) {
            visit(id)
          }
        }
      },
    },
    group: {
      name: 'builder-runtime',
      priority: 100,
      test: (id) => runtimeModules.has(id),
    },
  }
}
