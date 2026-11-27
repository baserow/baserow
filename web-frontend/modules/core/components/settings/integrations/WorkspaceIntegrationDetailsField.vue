<template>
  <div
    class="workspace-integration-details-field"
    :class="{ 'workspace-integration-details-field--error': errorMessage }"
  >
    <span
      v-if="subject"
      class="workspace-integration-details-field__subject"
      role="img"
      :title="subjectTypeName"
      :aria-label="subjectTypeName"
    >
      <component
        :is="subjectType.avatarComponent"
        :subject="subject"
        size="medium"
      />
    </span>
    <span class="workspace-integration-details-field__text" :title="details">
      {{ details }}
    </span>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useNuxtApp } from '#app'

const props = defineProps({
  row: { type: Object, required: true },
})

const nuxtApp = useNuxtApp()

const integrationType = computed(() =>
  nuxtApp.$registry.get('integration', props.row.type)
)

const errorMessage = computed(
  () => integrationType.value.getErrorMessage(props.row) || null
)

/**
 * The user or identity the integration acts as, shown with its avatar, which
 * tells which of the two it is.
 */
const subject = computed(() =>
  errorMessage.value ? null : integrationType.value.getSubject(props.row)
)

const subjectType = computed(() =>
  subject.value ? nuxtApp.$registry.get('subject', subject.value.type) : null
)

const subjectTypeName = computed(() =>
  subjectType.value?.getTypeDisplayName(subject.value)
)

/**
 * Why the integration can't be used when it's in error, otherwise its summary.
 * It reads the same for the integrations of the workspace and those of an
 * application: where it's listed already says which they are.
 */
const details = computed(
  () => errorMessage.value || integrationType.value.getSummary(props.row)
)
</script>
