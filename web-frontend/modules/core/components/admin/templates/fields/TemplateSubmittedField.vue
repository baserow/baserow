<template>
  <span v-if="row.submitted_on">
    {{ getHumanAgoLabel($i18n.t, row.submitted_on) }}
  </span>
</template>

<script setup>
import { useNuxtApp } from '#app'

import { getHumanAgoLabel } from '@baserow/modules/core/utils/date'

defineProps({
  row: {
    type: Object,
    required: true,
  },
})

const { $i18n } = useNuxtApp()
</script>
