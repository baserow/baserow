<template>
  <div v-if="row.author" class="templates-admin-author">
    <Avatar
      rounded
      size="small"
      :initials="authorName.charAt(0).toUpperCase()"
    ></Avatar>
    <div v-tooltip="row.author.email" class="templates-admin-author__name">
      {{ authorName }}
    </div>
  </div>
  <div v-else class="templates-admin-author templates-admin-author--deleted">
    {{ $t('templatesAdmin.deletedAuthor') }}
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  row: {
    type: Object,
    required: true,
  },
})

const authorName = computed(
  () => props.row.author?.first_name || props.row.author?.email || ''
)
</script>
