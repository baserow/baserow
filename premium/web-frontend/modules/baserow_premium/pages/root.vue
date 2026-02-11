<template>
  <NuxtPage />
</template>

<script setup>
definePageMeta({
  name: 'premium-root',
  layout: 'app',
  middleware: [
    'settings',
    'authenticated',
    'workspacesAndApplications',
    'pendingJobs',
  ],
})
</script>
