<template>
  <div class="auth__wrapper">
    <Login
      :display-header="true"
      :redirect-on-success="true"
      :invitation="invitation"
      :redirect-by-default="redirectByDefault"
    ></Login>
  </div>
</template>

<script>
import Login from '@baserow/modules/core/components/auth/Login'
import workspaceInvitationToken from '@baserow/modules/core/mixins/workspaceInvitationToken'

export default {
  components: { Login },
  layout: 'login',
  async asyncData({ app, route, store, redirect }) {
    if (store.getters['settings/get'].show_admin_signup_page === true) {
      return redirect({ name: 'signup' })
    } else if (store.getters['auth/isAuthenticated']) {
      return redirect({ name: 'dashboard' })
    }
    await store.dispatch('authProvider/fetchLoginOptions')
    return await workspaceInvitationToken.asyncData({ route, app })
  },
  head() {
    return {
      title: this.$t('login.title'),
      link: [
        {
          rel: 'canonical',
          href:
            this.$config.PUBLIC_WEB_FRONTEND_URL +
            this.$router.resolve({ name: 'login' }).href,
        },
      ],
    }
  },
  computed: {
    redirectByDefault() {
      if (this.$route.query.noredirect === null) {
        return false
      }
      return true
    },
  },
}
</script>
