<template>
  <form @submit.prevent @keydown.enter.prevent>
    <CustomStyle
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
      <Dropdown v-model="values.user_source_id" :show-search="false">
        <DropdownItem
          v-for="userSource in userSources"
          :key="userSource.id"
          :name="userSource.name"
          :value="userSource.id"
        />
      </Dropdown>
    </FormGroup>
    <CustomStyle
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
import CustomStyle from '@baserow/modules/builder/components/elements/components/forms/style/CustomStyle'
import InjectedFormulaInput from '@baserow/modules/core/components/formula/InjectedFormulaInput'

export default {
  name: 'AuthFormElementForm',
  components: {
    CustomStyle,
    InjectedFormulaInput,
  },
  mixins: [elementForm],
  inject: ['builder'],
  data() {
    return {
      allowedValues: ['user_source_id', 'styles', 'login_button_label'],
      values: {
        user_source_id: null,
        login_button_label: '',
        styles: {},
      },
    }
  },
  computed: {
    userSources() {
      return this.$store.getters['userSource/getUserSources'](this.builder)
    },
  },
  methods: {},
  validations() {
    return {}
  },
}
</script>
