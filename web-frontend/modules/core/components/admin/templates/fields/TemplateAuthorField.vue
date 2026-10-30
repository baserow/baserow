<template>
  <div v-if="row.author" class="templates-admin-author">
    <Avatar
      rounded
      size="small"
      :initials="row.author.first_name.charAt(0).toUpperCase()"
    ></Avatar>
    <div v-tooltip="row.author.email" class="templates-admin-author__name">
      {{ row.author.first_name }}
    </div>
  </div>
  <div v-else class="templates-admin-author templates-admin-author--deleted">
    {{ $t('templatesAdmin.deletedAuthor') }}
  </div>
</template>

<script setup>
defineProps({
  row: {
    type: Object,
    required: true,
  },
})
</script>
