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
        {{ $t('agent.deleteParticipatedConversation') }}
      </h2>
      <p :id="descriptionId">
        {{ $t('agent.deleteParticipatedConversationWarning') }}
      </p>
      <div class="actions actions--right actions--gap">
        <Button type="secondary" @click="modal.hide()">
          {{ $t('action.cancel') }}
        </Button>
        <Button type="secondary" @click="choose('leave')">
          {{ $t('agent.deleteForMe') }}
        </Button>
        <Button type="danger" @click="choose('delete')">
          {{ $t('agent.deleteForEveryone') }}
        </Button>
      </div>
    </template>
  </Modal>
</template>

<script setup>
import { ref, useId } from 'vue'

/** Asks whether to leave a private conversation others take part in, or delete it. */
const emit = defineEmits(['leave', 'delete'])

const modal = ref(null)
const conversation = ref(null)
const titleId = useId()
const descriptionId = useId()

function show(item) {
  conversation.value = item
  modal.value.show()
}

function choose(event) {
  emit(event, conversation.value)
  modal.value.hide()
}

defineExpose({ show })
</script>
