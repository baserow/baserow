<template>
  <form @submit.prevent @keydown.enter.prevent>
    <CustomStyleButton
      v-model="values.styles"
      style-key="input"
      :config-block-types="['input']"
      :theme="builder.theme"
    />
    <FormGroup
      :label="$t('authFormElementForm.userSource')"
      small-label
      required
      class="margin-bottom-2"
    >
      <UserSourceDropdown
        v-model="values.user_source_id"
        :builder="builder"
        :user-sources="userSources"
      ></UserSourceDropdown>
    </FormGroup>
    <CustomStyleButton
      v-model="values.styles"
      style-key="login_button"
      :config-block-types="['button']"
      :theme="builder.theme"
    />
    <FormGroup
      small-label
      :label="$t('authFormElementForm.loginButtonLabel')"
      class="margin-bottom-2"
      required
    >
      <InjectedFormulaInput
        v-model="values.login_button_label"
        :placeholder="$t('authFormElementForm.loginButtonLabelPlaceholder')"
      />
    </FormGroup>
  </form>
</template>

<script>
import elementForm from '@baserow/modules/builder/mixins/elementForm'
import CustomStyleButton from '@baserow/modules/builder/components/elements/components/forms/style/CustomStyleButton'
import InjectedFormulaInput from '@baserow/modules/core/components/formula/InjectedFormulaInput'
import UserSourceDropdown from '@baserow/modules/builder/components/userSource/UserSourceDropdown'

export default {
  name: 'AuthFormElementForm',
  components: {
    UserSourceDropdown,
    CustomStyleButton,
    InjectedFormulaInput,
  },
  mixins: [elementForm],
  inject: ['builder'],
  data() {
    return {
      allowedValues: ['user_source_id', 'styles', 'login_button_label'],
      values: {
        user_source_id: null,
        login_button_label: {},
        styles: {},
      },
    }
  },
  computed: {
    userSources() {
      return this.$store.getters['userSource/getUserSources'](this.builder)
    },
  },
}
</script>
