<script>
export default {
  async setup() {
    const store = useNuxtApp().$store
    const name = store.getters['auth/isAuthenticated'] ? 'dashboard' : 'login'
    await navigateTo({ name })
  },
}
</script>
