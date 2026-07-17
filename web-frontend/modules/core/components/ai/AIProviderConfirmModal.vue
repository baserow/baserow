<template>
  <Modal ref="modal" small @hidden="$emit('hidden')">
    <h2 class="box__title">{{ title }}</h2>
    <p>{{ message }}</p>
    <div class="actions">
      <ul class="action__links">
        <li>
          <a @click="hide()">{{ $t('action.cancel') }}</a>
        </li>
      </ul>
      <Button
        :type="danger ? 'danger' : 'primary'"
        :loading="loading"
        @click="$emit('confirm')"
      >
        {{ confirmLabel }}
      </Button>
    </div>
  </Modal>
</template>

<script>
import modal from '@baserow/modules/core/mixins/modal'

export default {
  name: 'AIProviderConfirmModal',
  mixins: [modal],
  props: {
    title: { type: String, required: true },
    message: { type: String, required: true },
    confirmLabel: { type: String, required: true },
    danger: { type: Boolean, default: false },
    loading: { type: Boolean, default: false },
  },
  emits: ['hidden', 'confirm'],
}
</script>
