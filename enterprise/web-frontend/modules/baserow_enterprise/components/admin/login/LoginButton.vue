<template>
  <Button
    tag="a"
    :href="loginUrl"
    target="_self"
    type="secondary"
    full-width
    size="large"
  >
    <AuthProviderIcon :icon="icon" />
    <span v-if="!small"> {{ $t('loginButton.continueWith') }} {{ name }}</span>
  </Button>
</template>

<script>
import AuthProviderIcon from '@baserow_enterprise/components/AuthProviderIcon.vue'

export default {
  name: 'OAuth2LoginButton',
  components: { AuthProviderIcon },
  props: {
    redirectUrl: {
      type: String,
      required: true,
    },
    name: {
      type: String,
      required: true,
    },
    icon: {
      type: String,
      required: true,
    },
    small: {
      type: Boolean,
      default: false,
      required: false,
    },
    invitation: {
      required: false,
      validator: (prop) => typeof prop === 'object' || prop === null,
      default: null,
    },
  },
  computed: {
    loginUrl() {
      const { workspaceInvitationToken } = this.$route.query
      const parsedUrl = new URL(this.redirectUrl)
      if (workspaceInvitationToken) {
        parsedUrl.searchParams.append(
          'workspace_invitation_token',
          workspaceInvitationToken
        )
      }
      return parsedUrl.toString()
    },
  },
}
</script>
