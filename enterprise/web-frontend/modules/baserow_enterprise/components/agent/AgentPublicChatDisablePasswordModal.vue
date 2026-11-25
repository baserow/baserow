<template>
  <Modal ref="modal" small>
    <template #content>
      <h2 class="box__title">
        {{ $t('agentChannels.disablePasswordTitle') }}
      </h2>
      <p class="box__description">
        {{ $t('agentChannels.disablePasswordDescription') }}
      </p>
      <div class="actions actions--right actions--gap">
        <Button type="secondary" size="large" @click="modal.hide()">
          {{ $t('action.cancel') }}
        </Button>
        <Button
          type="danger"
          size="large"
          class="agent-public-chat-disable-password-modal__disable"
          @click="disable"
        >
          {{ $t('agentChannels.disablePassword') }}
        </Button>
      </div>
    </template>
  </Modal>
</template>

<script setup>
import { ref } from 'vue'

/** Confirms removing the password of a public chat. */
const emit = defineEmits(['disable'])
const modal = ref(null)

function disable() {
  emit('disable')
  modal.value.hide()
}

defineExpose({ show: () => modal.value.show() })
</script>
