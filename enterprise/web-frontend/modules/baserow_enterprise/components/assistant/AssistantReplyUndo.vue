<template>
  <button
    v-if="consumedGroup !== groupId"
    v-tooltip="$t('assistantMessageActions.undo')"
    type="button"
    class="chat-message__action"
    :aria-label="$t('assistantMessageActions.undo')"
    :disabled="pending"
    @click="undo"
  >
    <i class="iconoir-undo" aria-hidden="true"></i>
  </button>
</template>

<script setup>
import { ref } from 'vue'
import { useStore } from 'vuex'
import { useI18n } from 'vue-i18n'
import { notifyIf } from '@baserow/modules/core/utils/error'
import { UNDO_REDO_RESULT_CODES } from '@baserow/modules/core/utils/undoRedoConstants'

const props = defineProps({ groupId: { type: String, required: true } })
const emit = defineEmits(['busy', 'done'])
const { t } = useI18n()
const store = useStore()
const pending = ref(false)
const consumedGroup = ref(null)

async function undo() {
  const groupId = props.groupId
  if (pending.value || consumedGroup.value === groupId) return
  pending.value = true
  emit('busy', true)
  try {
    const result = await store.dispatch('undoRedo/undo', {
      showLoadingToast: true,
      expectedActionGroupId: groupId,
    })
    if (!result) return
    consumedGroup.value = groupId
    store.commit('assistant/CLEAR_REPLY_UNDO', groupId)
    emit('done', groupId)
    if (result === UNDO_REDO_RESULT_CODES.NOTHING_TO_DO) {
      store.dispatch('toast/info', {
        title: t('assistantMessageActions.undoUnavailable'),
      })
    }
  } catch (error) {
    notifyIf(error)
  } finally {
    pending.value = false
    emit('busy', false)
  }
}
</script>
