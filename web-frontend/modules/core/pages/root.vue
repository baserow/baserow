<template>
  <NuxtPage />
</template>

<script setup>
definePageMeta({
  name: 'root',
  layout: 'app',
  middleware: [
    'settings',
    'authenticated',
    'impersonate',
    'workspacesAndApplications',
    'pendingJobs',
  ],
})
</script>
