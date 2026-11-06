<template>
  <Modal
    ref="modal"
    small
    class="agent-reject-modal"
    role="dialog"
    aria-modal="true"
    :aria-labelledby="titleId"
    :aria-describedby="descriptionId"
    @hidden="restoreFocus"
  >
    <template #content>
      <h2 :id="titleId" class="box__title">
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
        ref="reasonInput"
        v-model="reason"
        :rows="3"
        :maxlength="1000"
        :aria-label="$t('agent.rejectReason')"
        :aria-describedby="descriptionId"
        @keydown.shift.tab.exact.prevent="rejectButton.focus()"
      />
      <div class="agent-reject-modal__actions">
        <Button type="secondary" @click="modal.hide()">
          {{ $t('action.cancel') }}
        </Button>
        <Button
          ref="rejectButton"
          type="danger"
          @keydown.tab.exact.prevent="reasonInput.focus()"
          @click="reject"
          >{{ $t('agent.reject') }}</Button
        >
      </div>
    </template>
  </Modal>
</template>

<script setup>
import { nextTick, ref, useId } from 'vue'

/** Confirms held steps won't run, with an optional reason for the agent. */
const emit = defineEmits(['reject'])

const modal = ref(null)
const reasonInput = ref(null)
const rejectButton = ref(null)
const stepTitles = ref([])
const reason = ref('')
const titleId = useId()
const descriptionId = useId()
let opener = null

async function show(titles, trigger) {
  opener = trigger
  stepTitles.value = titles
  reason.value = ''
  modal.value.show()
  await nextTick()
  reasonInput.value?.focus()
}

function restoreFocus() {
  if (opener?.isConnected) opener.focus()
  opener = null
}

function reject() {
  emit('reject', reason.value.trim())
  modal.value.hide()
}

defineExpose({ show })
</script>
