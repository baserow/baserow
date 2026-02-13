<template>
  <NuxtPage />
</template>

<script setup>
definePageMeta({
  name: 'login-pages',
  layout: 'login',
  middleware: ['settings', 'urlCheck'],
})
</script>
