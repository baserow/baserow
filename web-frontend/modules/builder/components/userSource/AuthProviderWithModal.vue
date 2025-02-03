<template>
  <div>
    <div
      class="auth-provider-with-modal"
      :class="{ 'auth-provider-with-modal--error': inError }"
    >
      <Presentation
        class="flex-grow-1"
        :title="authProviderType.getProviderName(authProvider)"
        size="medium"
        avatar-color="neutral"
        :image="authProviderType.getIcon()"
        @click="onEdit"
      />
      <div class="auth-provider-with-modal__actions">
        <ButtonIcon
          type="secondary"
          icon="iconoir-edit"
          @click.prevent="onEdit"
        />
        <ButtonIcon
          type="secondary"
          icon="iconoir-bin"
          @click.prevent="onDelete"
        />
      </div>
    </div>
    <div v-if="inError" class="error">
      {{ $t('authProviderWithModal.authProviderInError') }}
    </div>
    <Modal ref="modal" keep-content @hidden="onHide">
      <h2 class="box__title">
        {{ $t('authProviderWithModal.title', { name: authProviderType.name }) }}
      </h2>
      <div>
        <slot name="default"></slot>
        <div class="actions actions--right">
          <Button size="large" @click.prevent="$refs.modal.hide()">
            {{ $t('action.close') }}
          </Button>
        </div>
      </div>
    </Modal>
  </div>
</template>

<script>
export default {
  name: 'AuthProviderWithModal',
  props: {
    authProviderType: {
      type: Object,
      required: true,
    },
    authProvider: {
      type: Object,
      required: true,
    },
    inError: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  methods: {
    onEdit() {
      this.$refs.modal.show()
    },
    onDelete() {
      this.$emit('delete')
    },
    onHide() {
      this.$emit('hidden')
    },
  },
}
</script>
