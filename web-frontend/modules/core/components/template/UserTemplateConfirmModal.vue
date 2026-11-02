<template>
  <Modal
    ref="modal"
    class="user-template-modal-wrapper user-template-modal-wrapper--small"
    :box-padding="false"
    :close-button="false"
    @hidden="emit('hidden')"
  >
    <div class="user-template-modal">
      <div class="user-template-modal__head">
        <h2 class="user-template-modal__title">{{ title }}</h2>
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
        <slot></slot>
      </div>

      <div class="user-template-modal__footer">
        <div class="user-template-modal__footer-actions">
          <Button type="secondary" @click="hide()">
            {{ $t('action.cancel') }}
          </Button>
          <Button
            :type="danger ? 'danger' : 'primary'"
            :loading="loading"
            :disabled="loading"
            @click="confirm"
          >
            {{ confirmLabel }}
          </Button>
        </div>
      </div>
    </div>
  </Modal>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'

import { notifyIf } from '@baserow/modules/core/utils/error'

/**
 * Asks the author to confirm a change of their template, then sends its request,
 * once per template.
 */
const props = defineProps({
  // The user's template as listed in their templates.
  template: {
    type: Object,
    required: true,
  },
  title: {
    type: String,
    required: true,
  },
  confirmLabel: {
    type: String,
    required: true,
  },
  danger: {
    type: Boolean,
    required: false,
    default: false,
  },
  // Sends the request for the template, and resolves with what `done` is emitted
  // with.
  request: {
    type: Function,
    required: true,
  },
})

// `done` is emitted with the id of the template, what the request resolved with
// and the `performance.now()` at which it was sent, also when the modal was closed
// or opened for another template while the request ran.
const emit = defineEmits(['done', 'hidden'])

const modal = ref(null)
// The ids of the templates whose request runs.
const pending = reactive(new Set())

const loading = computed(() => pending.has(props.template.id))

function show(...args) {
  modal.value.show(...args)
}

function hide(...args) {
  modal.value.hide(...args)
}

async function confirm() {
  const template = props.template
  const { id } = template
  if (pending.has(id)) {
    return
  }
  pending.add(id)
  const requestedAt = performance.now()
  try {
    const result = await props.request(template)
    emit('done', id, result, requestedAt)
    if (props.template.id === id) {
      hide()
    }
  } catch (error) {
    notifyIf(error, 'templates')
  } finally {
    pending.delete(id)
  }
}

defineExpose({ show, hide })
</script>
