<template>
  <div />
</template>

<script setup>
const store = useNuxtApp().$store
const name = store.getters['auth/isAuthenticated'] ? 'all-workspaces' : 'login'
await navigateTo({ name })
</script>
