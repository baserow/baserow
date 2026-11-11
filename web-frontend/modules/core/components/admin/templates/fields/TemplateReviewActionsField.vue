<template>
  <div class="templates-admin-actions" :data-template-id="row.id">
    <Button
      v-if="hasOpenReview"
      size="small"
      icon="iconoir-eye-empty"
      @click.stop="emit('open-review', row)"
    >
      {{ $t('templatesAdmin.review') }}
    </Button>
    <MoreField
      :row="row"
      @row-context="emit('row-context', $event)"
    ></MoreField>
  </div>
</template>

<script setup>
import { computed } from 'vue'

import MoreField from '@baserow/modules/core/components/crudTable/fields/MoreField'

const props = defineProps({
  row: {
    type: Object,
    required: true,
  },
})

const emit = defineEmits(['open-review', 'row-context'])

const hasOpenReview = computed(() =>
  ['in_review', 'rejected'].includes(props.row.state)
)
</script>
