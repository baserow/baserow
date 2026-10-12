<template>
  <div></div>
</template>

<script setup>
import WorkspaceService from '@baserow/modules/core/services/workspace'

const route = useRoute()
const { $store: store, $client, $registry } = useNuxtApp()

const token = route.params.token

// Fetch the invitation data
const { data: invitation, error } = await useAsyncData(
  'workspace-invitation',
  async () => {
    const { data } =
      await WorkspaceService($client).fetchInvitationByToken(token)
    return data
  }
)

// Handle error - invitation not found or already accepted
if (error.value) {
  // If user is authenticated, redirect to the all workspaces homepage
  if (store.getters['auth/isAuthenticated']) {
    await navigateTo({ name: 'all-workspaces' }, { replace: true })
  } else {
    // Otherwise redirect to login
    await navigateTo({ name: 'login' }, { replace: true })
  }
}

// Handle the invitation after data is fetched
if (invitation.value) {
  const inv = invitation.value

  // If the authenticated user has the same email address we can accept the invitation
  // right away and redirect to the workspace.
  if (
    store.getters['auth/isAuthenticated'] &&
    store.getters['auth/getUsername'] === inv.email
  ) {
    try {
      // An invitation can lead to one object of the workspace instead of the
      // workspace itself. The target types know where, and must be asked before
      // accepting because the invitation is deleted afterwards. A failing lookup
      // must not stand in the way of accepting the invitation.
      let landingRoute = null
      for (const targetType of $registry.getOrderedList('invitationTarget')) {
        try {
          landingRoute = await targetType.getLandingRoute(token, inv)
        } catch {
          landingRoute = null
        }
        if (landingRoute) {
          break
        }
      }

      // Accept the invitation - returns the workspace data
      const { data: workspace } = await WorkspaceService(
        $client
      ).acceptInvitation(inv.id)

      // Clear workspace loaded state so it gets refetched on next page
      store.commit('workspace/SET_LOADED', false)
      store.commit('application/SET_LOADED', false)

      // Redirect to the object the invitation leads to, or the workspace.
      await navigateTo(
        landingRoute || {
          name: 'workspace',
          params: { workspaceId: workspace.id },
        },
        { replace: true }
      )
    } catch {
      // If accepting fails (e.g., already accepted), redirect to the all
      // workspaces homepage
      await navigateTo({ name: 'all-workspaces' }, { replace: true })
    }
  } else {
    // Depending on if the email address already exists we redirect the user to either
    // the login or signup page.
    const name = inv.email_exists ? 'login' : 'signup'
    await navigateTo(
      { name, query: { workspaceInvitationToken: token } },
      { replace: true }
    )
  }
}
</script>
