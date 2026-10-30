<template>
  <Modal
    ref="modal"
    class="user-template-modal-wrapper user-template-modal-wrapper--small"
    :box-padding="false"
    :close-button="false"
  >
    <form class="user-template-modal" @submit.prevent="submit">
      <div class="user-template-modal__head">
        <h2 class="user-template-modal__title">
          {{ $t('rejectTemplateModal.title', { name: template.name }) }}
        </h2>
        <button
          type="button"
          class="user-template-modal__head-action user-template-modal__close"
          :title="$t('action.close')"
          @click="hide()"
        >
          <i class="iconoir-cancel"></i>
        </button>
      </div>

      <div class="user-template-modal__body">
        <p class="user-template-modal__description">
          {{
            $t(
              editOnly
                ? 'rejectTemplateModal.editDescription'
                : 'rejectTemplateModal.description'
            )
          }}
        </p>
        <FormGroup
          small-label
          :label="$t('rejectTemplateModal.reasonLabel')"
          required
        >
          <FormInput
            v-model="reason"
            :maxlength="MAX_REASON_LENGTH"
            :placeholder="$t('rejectTemplateModal.reasonPlaceholder')"
          ></FormInput>
        </FormGroup>
      </div>

      <div class="user-template-modal__footer">
        <div class="user-template-modal__footer-actions">
          <Button type="secondary" @click="hide()">
            {{ $t('action.cancel') }}
          </Button>
          <Button
            type="danger"
            button-type="submit"
            :loading="loading"
            :disabled="loading || !trimmedReason"
          >
            {{ $t('rejectTemplateModal.reject') }}
          </Button>
        </div>
      </div>
    </form>
  </Modal>
</template>

<script setup>
import { computed, ref } from 'vue'

// The longest reason the server accepts.
const MAX_REASON_LENGTH = 1000

/**
 * Asks for the reason why a template is rejected, which its author sees. Only
 * emits it, the caller rejects the template.
 */
defineProps({
  template: {
    type: Object,
    required: true,
  },
  loading: {
    type: Boolean,
    required: false,
    default: false,
  },
  // Whether only the latest change of a listed template is rejected, which
  // leaves the approved version listed.
  editOnly: {
    type: Boolean,
    required: false,
    default: false,
  },
})

const emit = defineEmits(['submit'])

const modal = ref(null)
const reason = ref('')

const trimmedReason = computed(() => reason.value.trim())

function show(...args) {
  reason.value = ''
  modal.value.show(...args)
}

function hide(...args) {
  modal.value.hide(...args)
}

function submit() {
  if (trimmedReason.value) {
    emit('submit', trimmedReason.value)
  }
}

defineExpose({ show, hide })
</script>
