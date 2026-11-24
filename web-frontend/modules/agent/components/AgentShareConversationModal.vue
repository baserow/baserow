<template>
  <Modal
    ref="modal"
    small
    role="dialog"
    aria-modal="true"
    :aria-labelledby="titleId"
    :aria-describedby="descriptionId"
  >
    <template #content>
      <h2 :id="titleId" class="box__title">
        {{ $t('agent.shareConversation') }}
      </h2>
      <p :id="descriptionId">{{ $t('agent.shareConversationWarning') }}</p>
      <div class="actions actions--right actions--gap">
        <Button type="secondary" @click="modal.hide()">
          {{ $t('action.cancel') }}
        </Button>
        <Button @click="share">{{ $t('agent.share') }}</Button>
      </div>
    </template>
  </Modal>
</template>

<script setup>
import { ref, useId } from 'vue'

/** Confirms sharing a private conversation, which can't be undone. */
const emit = defineEmits(['share'])

const modal = ref(null)
const conversation = ref(null)
const titleId = useId()
const descriptionId = useId()

function show(item) {
  conversation.value = item
  modal.value.show()
}

function share() {
  emit('share', conversation.value)
  modal.value.hide()
}

defineExpose({ show })
</script>
