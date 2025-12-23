<template>
  <div />
</template>

<script setup>
const store = useNuxtApp().$store
const name = store.getters['auth/isAuthenticated'] ? 'dashboard' : 'login'
await navigateTo({ name })
</script>
