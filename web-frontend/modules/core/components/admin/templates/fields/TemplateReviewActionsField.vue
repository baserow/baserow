<template>
  <div class="templates-admin-actions">
    <Button
      v-if="reviewable"
      size="small"
      icon="iconoir-eye-empty"
      @click.stop="emit('review', row)"
    >
      {{ $t('templatesAdmin.review') }}
    </Button>
    <Button
      v-else-if="unlists"
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

import { rejectUnlists } from '@baserow/modules/core/composables/useTemplateReview'

/**
 * The review actions of a template on the admin page. A template in review or
 * rejected is reviewed in its preview, which `review` is emitted for. A
 * published one is unlisted, which asks for a reason in the modal of the table,
 * which `reject` is emitted for, so that the modals outlive the row when the
 * list is refreshed.
 */
const props = defineProps({
  row: {
    type: Object,
    required: true,
  },
})

const emit = defineEmits(['review', 'reject'])

const reviewable = computed(() =>
  ['in_review', 'rejected'].includes(props.row.state)
)
const unlists = computed(() => rejectUnlists(props.row))
</script>
