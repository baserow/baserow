<template>
  <i18n-t
    class="templates-admin-used"
    keypath="templatesAdmin.usedTimes"
    :plural="row.install_count"
    scope="global"
    tag="span"
  >
    <template #count>
      <span class="templates-admin-used__count">{{ row.install_count }}</span>
    </template>
  </i18n-t>
</template>

<script setup>
defineProps({
  row: {
    type: Object,
    required: true,
  },
})
</script>
