<template>
  <input
    type="checkbox"
    class="management-table__boolean"
    :checked="Boolean(row[column.key]?.is_enabled)"
    disabled
    :aria-label="
      $t(
        row[column.key]?.is_enabled
          ? 'twoFactorAuthField.enabled'
          : 'twoFactorAuthField.disabled'
      )
    "
    :title="
      $t(
        row[column.key]?.is_enabled
          ? 'twoFactorAuthField.enabled'
          : 'twoFactorAuthField.disabled'
      )
    "
  />
</template>

<script setup>
defineProps({
  row: { type: Object, required: true },
  column: { type: Object, required: true },
})
</script>
