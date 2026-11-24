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
        {{ $t(warning) }}
      </p>
      <div class="actions actions--right actions--gap">
        <Button type="secondary" @click="modal.hide()">
          {{ $t('action.cancel') }}
        </Button>
        <Button type="secondary" @click="choose('leave')">
          {{ $t('agent.deleteForMe') }}
        </Button>
        <Button v-if="forEveryone" type="danger" @click="choose('delete')">
          {{ $t('agent.deleteForEveryone') }}
        </Button>
      </div>
    </template>
  </Modal>
</template>

<script setup>
import { computed, ref, useId } from 'vue'

/** Asks whether to leave a private conversation others take part in, or delete it. */
const emit = defineEmits(['leave', 'delete'])

const modal = ref(null)
const conversation = ref(null)
const forEveryone = ref(true)
const titleId = useId()
const descriptionId = useId()
const warning = computed(() => {
  if (forEveryone.value) return 'agent.deleteParticipatedConversationWarning'
  return conversation.value?.participants.length > 1
    ? 'agent.leaveConversationWarning'
    : 'agent.leaveLastConversationWarning'
})

/**
 * @param {object} item The conversation.
 * @param {object} [options]
 * @param {boolean} [options.forEveryone] Whether its owner may also delete it
 *   for everyone, rather than only leave it.
 */
function show(item, { forEveryone: everyone = true } = {}) {
  conversation.value = item
  forEveryone.value = everyone
  modal.value.show()
}

function choose(event) {
  emit(event, conversation.value)
  modal.value.hide()
}

defineExpose({ show })
</script>
