<template>
  <NuxtPage />
</template>

<script setup>
definePageMeta({
  name: 'database-root',
  layout: 'app',
  middleware: [
    'settings',
    'authenticated',
    'workspacesAndApplications',
    'pendingJobs',
  ],
})
</script>
