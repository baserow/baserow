<template>
  <div>
    <div
      class="common-saml-setting-form"
      :class="{ 'common-saml-setting-form--error': inError }"
    >
      <Presentation
        class="flex-grow-1"
        :title="authProviderType.getProviderName(authProvider)"
        size="medium"
        avatar-color="neutral"
        :image="authProviderType.getIcon()"
        @click="onEdit"
      />
      <div class="common-saml-setting-form__actions">
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
      {{ $t('commonSamlSettingForm.authProviderInError') }}
    </div>
    <CommonSamlSettingModal
      ref="samlModal"
      v-bind="$props"
      :integration="integration"
      :user-source="userSource"
      @form-valid="onFormValid($event)"
      v-on="$listeners"
    ></CommonSamlSettingModal>
  </div>
</template>

<script>
import authProviderForm from '@baserow/modules/core/mixins/authProviderForm'
import CommonSamlSettingModal from '@baserow_enterprise/integrations/common/components/CommonSamlSettingModal'

export default {
  name: 'CommonSamlSettingForm',
  components: { CommonSamlSettingModal },
  mixins: [authProviderForm],
  inject: ['builder'],
  props: {
    integration: {
      type: Object,
      required: true,
    },
    userSource: {
      type: Object,
      required: true,
    },
  },
  data() {
    return { inError: false }
  },
  methods: {
    onFormValid(value) {
      this.inError = !value
    },
    onEdit() {
      this.$refs.samlModal.show()
    },
    onDelete() {
      this.$emit('delete')
    },
    handleServerError(error) {
      if (this.$refs.samlModal.handleServerError(error)) {
        this.inError = true
        return true
      }
      return false
    },
  },
}
</script>
