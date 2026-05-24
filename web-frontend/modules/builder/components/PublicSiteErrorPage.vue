<template>
  <div v-if="!redirecting" class="placeholder">
    <div class="placeholder__logo">
      <a
        :href="
          $router.resolve({
            name: routeName,
            params: { pathMatch: '' },
          }).fullPath
        "
        @click.prevent="
          clearAndNavigate({
            name: routeName,
            params: { pathMatch: '' },
          })
        "
      >
        <Logo class="placeholder__logo-image" />
      </a>
    </div>
    <h1 class="placeholder__title">{{ message }}</h1>
    <p v-if="error.statusCode === 404" class="placeholder__content">
      {{ $t('errorLayout.notFound') }}
    </p>
    <p v-else class="placeholder__content">{{ content }}</p>
    <div class="placeholder__action">
      <Button type="primary" icon="iconoir-home" size="large" @click="onHome()">
        {{ $t('action.backToHome') }}
      </Button>
    </div>
  </div>
</template>

<script>
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
      return this.error.content || this.$t('errorLayout.error')
    },
    routeName() {
      return this.$route.name
    },
  },
  methods: {
    clearAndNavigate(to) {
      window.location.replace(this.$router.resolve(to).fullPath)
    },
    async onHome() {
      if (
        ['application-builder-page', 'application-builder-preview'].includes(
          this.routeName
        )
      ) {
        if (this.$route.params.pathMatch === '/') {
          // Reload the current page
          this.$router.go(0)
        } else {
          // Navigate to the home route
          this.clearAndNavigate({
            name: this.routeName,
            params: { pathMatch: '' },
            query: null, // Remove query parameters
          })
        }
      }
    },
  },
}
</script>
