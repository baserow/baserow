<template>
  <div class="management-name-field">
    <component
      :is="column.additionalProps.avatarComponent"
      v-if="column.additionalProps.avatarComponent"
      :subject="row"
      size="large"
      aria-hidden="true"
    />
    <Avatar
      v-else
      :icon="column.additionalProps.icon || ''"
      :initials="column.additionalProps.icon ? '' : initials"
      :color="column.additionalProps.color || 'blue'"
      :rounded="!column.additionalProps.icon"
      size="large"
      aria-hidden="true"
    />
    <span class="management-name-field__name" :title="row[column.key]">{{
      row[column.key]
    }}</span>
    <Badge
      v-if="
        row.user_id != null && row.user_id === column.additionalProps.userId
      "
      size="small"
    >
      {{ $t('managementPages.you') }}
    </Badge>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import Avatar from '@baserow/modules/core/components/Avatar'
import Badge from '@baserow/modules/core/components/Badge'
import nameAbbreviation from '@baserow/modules/core/filters/nameAbbreviation'

const props = defineProps({
  row: { type: Object, required: true },
  column: { type: Object, required: true },
})

const initials = computed(() => nameAbbreviation(props.row[props.column.key]))
</script>
