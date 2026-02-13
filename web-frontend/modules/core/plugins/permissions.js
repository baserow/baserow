const alreadyWarned = new Set()

export default defineNuxtPlugin({
  name: 'permissions',
  dependsOn: ['i18n', 'store'],
  async setup(nuxtApp) {
    const { $registry, $store } = nuxtApp

    let hasPermission

    if (import.meta.env.VITEST) {
      hasPermission = () => true
    } else {
      hasPermission = (operation, context, workspaceId = null) => {
        let perms = []

        if (workspaceId === null) {
          perms = $store.getters['auth/getGlobalUserPermissions']
        } else {
          const workspace = $store.getters['workspace/get'](workspaceId)
          if (workspace === undefined || !workspace._.permissionsLoaded) {
            perms = $store.getters['auth/getGlobalUserPermissions']
          } else {
            perms = workspace._.permissions
          }
        }

        for (const perm of perms) {
          const { name, permissions } = perm
          let manager

          try {
            manager = $registry.get('permissionManager', name)
          } catch (e) {
            // If a permission manager is missing we show a warning once.
            if (!alreadyWarned.has(name)) {
              alreadyWarned.add(name)
              console.warn(`Permission manager '${name}' missing in registry`)
            }
            continue
          }

          try {
            const result = manager.hasPermission(
              permissions,
              operation,
              context,
              workspaceId
            )

            if ([true, false].includes(result)) {
              return result
            }
          } catch (e) {
            console.warn('Error during permission check', e)
            return false
          }
        }
        return false
      }
    }

    nuxtApp.provide('hasPermission', hasPermission)
  },
})
