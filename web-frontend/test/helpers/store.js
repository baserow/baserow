import { flushPromises } from '@vue/test-utils'

/**
 * Adds the workspaces with their permissions loaded, so that they aren't
 * fetched, selects the first one and adds the applications.
 */
export const seedWorkspaces = async (store, workspaces, applications = []) => {
  for (const workspace of workspaces) {
    await store.dispatch('workspace/forceCreate', workspace)
    store.commit('workspace/SET_PERMISSIONS', {
      workspaceId: workspace.id,
      permissions: [],
    })
  }
  store.commit(
    'workspace/SET_SELECTED',
    store.getters['workspace/get'](workspaces[0].id)
  )
  for (const application of applications) {
    await store.dispatch('application/forceCreate', application)
  }
}

/**
 * Updates the job in the store like a job poll does, and lets the components
 * react to it.
 */
export const updateJob = async (store, id, data) => {
  const job = store.getters['job/get'](id)
  await store.dispatch('job/forceUpdate', { job, data })
  await flushPromises()
}
