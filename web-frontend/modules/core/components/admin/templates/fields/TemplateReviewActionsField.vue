<template>
  <div class="templates-admin-actions">
    <Button
      v-if="hasOpenReview"
      size="small"
      icon="iconoir-eye-empty"
      @click.stop="emit('open-review', row)"
    >
      {{ $t('templatesAdmin.review') }}
    </Button>
    <Button
      v-else-if="row.reject_unlists"
      type="secondary"
      size="small"
      icon="iconoir-eye-off"
      @click.stop="emit('reject', row)"
    >
      {{ $t('templatesAdmin.unlist') }}
    </Button>
  </div>
</template>

<script setup>
import { computed } from 'vue'

/**
 * `open-review` previews a template in review or rejected, `reject` unlists a
 * public one. The modals are the table's, so they outlive the row.
 */
const props = defineProps({
  row: {
    type: Object,
    required: true,
  },
})

const emit = defineEmits(['open-review', 'reject'])

const hasOpenReview = computed(() =>
  ['in_review', 'rejected'].includes(props.row.state)
)
</script>
