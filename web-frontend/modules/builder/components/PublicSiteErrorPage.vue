<template>
  <div v-if="!redirecting" class="placeholder">
    <div class="placeholder__logo">
      <a
        v-if="!shouldCloseTab"
        :href="$router.resolve(homeRoute).fullPath"
        @click.prevent="clearAndNavigate(homeRoute)"
      >
        <Logo class="placeholder__logo-image" />
      </a>
      <Logo v-else class="placeholder__logo-image" />
    </div>
    <h1 class="placeholder__title">{{ message }}</h1>
    <p v-if="error.statusCode === 404" class="placeholder__content">
      {{ $t('errorLayout.notFound') }}
    </p>
    <p v-else class="placeholder__content">{{ content }}</p>
    <div class="placeholder__action">
      <Button
        v-if="shouldCloseTab"
        type="primary"
        icon="iconoir-cancel"
        size="large"
        @click="closeTab"
      >
        {{ $t('action.close') }}
      </Button>
      <Button
        v-else
        tag="a"
        :href="$router.resolve(homeRoute).fullPath"
        type="primary"
        icon="iconoir-home"
        size="large"
        @click.prevent="onHome"
      >
        {{ $t('action.backToHome') }}
      </Button>
    </div>
  </div>
</template>

<script>
import { useHead } from '#app'
import { useI18n } from 'vue-i18n'

export default {
  props: {
    error: {
      type: Object,
      required: true,
    },
  },
  setup(props) {
    const { t } = useI18n()
    useHead(() => ({
      title: props.error.message || t('errorLayout.wrong'),
    }))
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
      return this.error.content || this.$t('errorLayout.error')
    },
    shouldCloseTab() {
      return this.error.data?.closeTab === true
    },
    routeName() {
      return this.$route.name
    },
    homeRoute() {
      return {
        name: this.routeName,
        params: {
          builderId: this.$route.params.builderId,
          pathMatch: '',
        },
        query: null,
      }
    },
  },
  methods: {
    closeTab() {
      window.close()
    },
    clearAndNavigate(to) {
      window.location.replace(this.$router.resolve(to).fullPath)
    },
    onHome() {
      const homePath = this.$router.resolve(this.homeRoute).path
      if (this.$route.path === homePath) {
        this.$router.go(0)
      } else {
        this.clearAndNavigate(this.homeRoute)
      }
    },
  },
}
</script>
