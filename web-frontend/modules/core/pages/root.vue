<template>
  <NuxtPage />
</template>

<script setup>
definePageMeta({
  name: 'root',
  layout: 'app',
  middleware: ['settings', 'authenticated', 'pendingJobs'],
})
</script>
