<template>
  <div v-if="!redirecting" class="placeholder">
    <div class="placeholder__logo">
      <nuxt-link :to="{ name: 'index' }">
        <Logo class="placeholder__logo-image" />
      </nuxt-link>
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
        {{ $t('errorLayout.refresh') }}</Button
      >

      <Button
        v-else-if="isAuthenticated && currentRouteName !== 'dashboard'"
        tag="nuxt-link"
        :to="{ name: 'dashboard' }"
        type="primary"
        size="large"
        icon="iconoir-nav-arrow-left"
      >
        {{ $t('errorLayout.backDashboard') }}</Button
      >

      <Button
        v-else
        tag="nuxt-link"
        :to="{ name: 'login' }"
        type="primary"
        size="large"
        icon="iconoir-nav-arrow-left"
      >
        {{ $t('errorLayout.backLogin') }}</Button
      >
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
  head() {
    return {
      title: this.message,
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
    refresh() {
      location.reload()
    },
  },
}
</script>
