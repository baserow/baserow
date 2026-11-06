<template>
  <Modal ref="modal" small class="agent-reject-modal">
    <template #content>
      <h2 class="box__title">
        {{
          $t(
            stepTitles.length > 1
              ? 'agent.rejectStepsTitle'
              : 'agent.rejectStepTitle'
          )
        }}
      </h2>
      <p :id="descriptionId" class="agent-reject-modal__description">
        {{
          stepTitles.length > 1
            ? $t('agent.rejectStepsDescription', { count: stepTitles.length })
            : $t('agent.rejectStepDescription', { step: stepTitles[0] })
        }}
      </p>
      <FormTextarea
        v-model="reason"
        :rows="3"
        :maxlength="1000"
        :aria-label="$t('agent.rejectReason')"
        :aria-describedby="descriptionId"
      />
      <div class="agent-reject-modal__actions">
        <Button type="secondary" @click="modal.hide()">
          {{ $t('action.cancel') }}
        </Button>
        <Button type="danger" @click="reject">{{ $t('agent.reject') }}</Button>
      </div>
    </template>
  </Modal>
</template>

<script setup>
import { ref, useId } from 'vue'

/** Confirms held steps won't run, with an optional reason for the agent. */
const emit = defineEmits(['reject'])

const modal = ref(null)
const stepTitles = ref([])
const reason = ref('')
const descriptionId = useId()

function show(titles) {
  stepTitles.value = titles
  reason.value = ''
  modal.value.show()
}

function reject() {
  emit('reject', reason.value.trim())
  modal.value.hide()
}

defineExpose({ show })
</script>
