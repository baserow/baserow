<template>
  <div></div>
</template>

<script setup>
import WorkspaceService from '@baserow/modules/core/services/workspace'

definePageMeta({
  middleware: ['settings'],
})

const route = useRoute()
const { $store: store, $client } = useNuxtApp()

const slug = route.params.slug

// Fetch the invitation link data
const { data: invitationLink, error } = await useAsyncData(
  `invitation-link-${slug}`,
  async () => {
    const { data } =
      await WorkspaceService($client).fetchInvitationLinkBySlug(slug)
    return data
  }
)

// Handle error - the link doesn't exist (anymore)
if (error.value) {
  if (store.getters['auth/isAuthenticated']) {
    await navigateTo({ name: 'all-workspaces' }, { replace: true })
  } else {
    await navigateTo({ name: 'login' }, { replace: true })
  }
}

if (invitationLink.value) {
  if (store.getters['auth/isAuthenticated']) {
    // Anyone who is logged in joins right away. Someone who is already a member
    // keeps their role and simply lands in the workspace.
    try {
      const { data: workspace } =
        await WorkspaceService($client).joinInvitationLink(slug)

      // Clear workspace loaded state so it gets refetched on next page
      store.commit('workspace/SET_LOADED', false)
      store.commit('application/SET_LOADED', false)

      await navigateTo(
        { name: 'workspace', params: { workspaceId: workspace.id } },
        { replace: true }
      )
    } catch {
      await navigateTo({ name: 'all-workspaces' }, { replace: true })
    }
  } else {
    // A link doesn't tell who opens it, so new people sign up from it when they
    // are allowed to, and everyone else logs in and comes back here.
    const settings = store.getters['settings/get']
    const signupAllowed =
      settings.allow_new_signups ||
      settings.allow_signups_via_workspace_invitations
    await navigateTo(
      signupAllowed
        ? { name: 'signup', query: { invitationLinkSlug: slug } }
        : { name: 'login', query: { original: route.fullPath } },
      { replace: true }
    )
  }
}
</script>
