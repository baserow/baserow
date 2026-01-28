/*export default function ({ app }, inject) {
  /**
   * Check the permission for the given operation with the given context.
   *
   * This function uses all the registered permissions to check the permission.
   * @param {string} operation
   * @param {object} context
   * @param {number|null} workspaceId
   * @returns True if the operation is permitted, false otherwise.
   *\/
  const hasPermission = (operation, context, workspaceId = null) => {
    const { store, $registry } = app

    let perms = []

    // If we receive a null `workspaceId`, then we're testing an operation
    // that is outside the scope of a workspace, so we'll need to use the
    // user's permissions for our `perms`.
    if (workspaceId === null) {
      perms = store.getters['auth/getGlobalUserPermissions']
    } else {
      // If we receive a `workspaceId`, then we can use the
      // permissions which are specific to this workspace.
      const workspace = store.getters['workspace/get'](workspaceId)
      // If the workspace is not found
      // it might be a template so we return the global perms.
      if (workspace === undefined || !workspace._.permissionsLoaded) {
        perms = store.getters['auth/getGlobalUserPermissions']
      } else {
        perms = workspace._.permissions
      }
    }

    // Check all permission managers whether one accepts or refuses the operation
    for (const perm of perms) {
      const { name, permissions } = perm
      const manager = $registry.get('permissionManager', name)
      const result = manager.hasPermission(
        permissions,
        operation,
        context,
        workspaceId
      )

      if ([true, false].includes(result)) {
        return result
      }
    }
    return false
  }
  inject('hasPermission', hasPermission)
}
*/

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
