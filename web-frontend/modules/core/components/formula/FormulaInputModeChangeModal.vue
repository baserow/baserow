<template>
  <Modal
    ref="modal"
    class="formula-input-explorer-context__advanced-mode-modal"
  >
    <h2 class="box__title">{{ title }}</h2>
    <p>{{ $t('formulaInputExplorerContext.modalMessage') }}</p>

    <div class="actions actions--right actions--gap margin-bottom-0">
      <Button type="secondary" size="large" @click="hide">
        {{ $t('action.cancel') }}
      </Button>
      <Button type="danger" size="large" @click="confirm">
        {{ confirmLabel }}
      </Button>
    </div>
  </Modal>
</template>

<script>
export default {
  name: 'FormulaInputModeChangeModal',
  props: {
    title: {
      type: String,
      required: true,
    },
    confirmLabel: {
      type: String,
      required: true,
    },
  },
  emits: ['confirm'],
  methods: {
    show() {
      this.$refs.modal.show()
    },
    hide() {
      this.$refs.modal.hide()
    },
    confirm() {
      this.hide()
      this.$emit('confirm')
    },
  },
}
</script>
