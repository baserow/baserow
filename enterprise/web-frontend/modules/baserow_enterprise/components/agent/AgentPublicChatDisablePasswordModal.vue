<template>
  <Modal ref="modal" small>
    <template #content>
      <h2 class="box__title">
        {{ $t('agentChannels.disablePasswordTitle') }}
      </h2>
      <Error :error="error" />
      <p class="box__description">
        {{ $t('agentChannels.disablePasswordDescription') }}
      </p>
      <div class="actions actions--right actions--gap">
        <Button
          type="secondary"
          size="large"
          :disabled="loading"
          @click="modal.hide()"
        >
          {{ $t('action.cancel') }}
        </Button>
        <Button
          type="danger"
          size="large"
          class="agent-public-chat-disable-password-modal__disable"
          :loading="loading"
          :disabled="loading"
          @click="submit"
        >
          {{ $t('agentChannels.disablePassword') }}
        </Button>
      </div>
    </template>
  </Modal>
</template>

<script setup>
import { reactive, ref } from 'vue'

/** Confirms removing a public chat's password and stays open until it's gone. */
const props = defineProps({
  /** Removes the password, and rejects when that fails. */
  disable: { type: Function, required: true },
})
const modal = ref(null)
const loading = ref(false)
const error = reactive({ visible: false, title: '', message: '' })

function show() {
  error.visible = false
  modal.value.show()
}

async function submit() {
  error.visible = false
  loading.value = true
  try {
    await props.disable()
    modal.value.hide()
  } catch (caught) {
    if (!caught.handler) throw caught
    Object.assign(error, caught.handler.getMessage('channel'), {
      visible: true,
    })
    caught.handler.handled()
  } finally {
    loading.value = false
  }
}

defineExpose({ show })
</script>
