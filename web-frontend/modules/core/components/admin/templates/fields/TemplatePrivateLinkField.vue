<template>
  <i
    v-tooltip="label"
    :aria-label="label"
    role="img"
    class="templates-admin-private-link"
    :class="
      row.private_link
        ? 'iconoir-check templates-admin-private-link--on'
        : 'iconoir-cancel templates-admin-private-link--off'
    "
  ></i>
</template>

<script setup>
import { computed } from 'vue'
import { useNuxtApp } from '#app'

const props = defineProps({
  row: {
    type: Object,
    required: true,
  },
})

const { $i18n } = useNuxtApp()

const label = computed(() =>
  $i18n.t(
    props.row.private_link
      ? 'templatesAdmin.hasPrivateLink'
      : 'templatesAdmin.noPrivateLink'
  )
)
</script>
