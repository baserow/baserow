<template>
  <div v-if="!redirecting" class="placeholder">
    <div class="placeholder__logo">
      <a
        :href="$router.resolve({ name: 'index' }).fullPath"
        @click.prevent="clearAndNavigate({ name: 'index' })"
      >
        <Logo class="placeholder__logo-image" />
      </a>
    </div>
    <h1 class="placeholder__title">{{ message }}</h1>
    <p v-if="error.statusCode === 404" class="placeholder__content">
      {{ $t('errorLayout.notFound') }}
    </p>
    <p v-else class="placeholder__content">{{ content }}</p>
    <div v-if="showBackButton" class="placeholder__action">
      <Button
        v-if="isAuthenticated && currentRouteName === 'dashboard'"
        type="primary"
        icon="iconoir-redo"
        @click="refresh"
      >
        {{ $t('errorLayout.refresh') }}
      </Button>

      <Button
        v-else-if="isAuthenticated && currentRouteName !== 'dashboard'"
        tag="a"
        :href="$router.resolve({ name: 'dashboard' }).fullPath"
        type="primary"
        size="large"
        icon="iconoir-nav-arrow-left"
        @click.prevent="clearAndNavigate({ name: 'dashboard' })"
      >
        {{ $t('errorLayout.backDashboard') }}
      </Button>

      <Button
        v-else
        tag="a"
        :href="$router.resolve({ name: 'login' }).fullPath"
        type="primary"
        size="large"
        icon="iconoir-nav-arrow-left"
        @click.prevent="clearAndNavigate({ name: 'login' })"
      >
        {{ $t('errorLayout.backLogin') }}
      </Button>
    </div>
  </div>
</template>

<script>
import { mapGetters } from 'vuex'
import { logoutAndRedirectToLogin } from '@baserow/modules/core/utils/auth'

export default {
  props: {
    error: {
      type: Object,
      required: true,
    },
  },
  data() {
    return {
      redirecting: false,
    }
  },
  computed: {
    statusCode() {
      return (this.error && this.error.statusCode) || 500
    },
    message() {
      return this.error.message || this.$t('errorLayout.wrong')
    },
    content() {
      return this.error.content ?? this.$t('errorLayout.error')
    },
    showBackButton() {
      return !this.error.hideBackButton
    },
    currentRouteName() {
      return this.$route.name
    },
    ...mapGetters({
      isAuthenticated: 'auth/isAuthenticated',
    }),
  },
  async created() {
    const showSessionExpiredToast =
      this.$store.getters['auth/isUserSessionExpired']
    if (showSessionExpiredToast) {
      this.redirecting = true
      await logoutAndRedirectToLogin(
        this.$router,
        this.$store,
        showSessionExpiredToast
      )
    }
  },
  methods: {
    clearAndNavigate(to) {
      window.location.replace(this.$router.resolve(to).fullPath)
    },
    refresh() {
      location.reload()
    },
  },
}
</script>
