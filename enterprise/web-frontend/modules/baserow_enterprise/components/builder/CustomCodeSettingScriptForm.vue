<template>
  <div class="custom-code-setting-script-form__wrapper">
    <div class="custom-code-setting-script-form">
      <div
        class="custom-code-setting-script-form__handle"
        data-sortable-handle
      />
      <div class="custom-code-setting-script-form__header">
        <FormRow>
          <FormGroup
            :label="$t('customCodeSettingScriptForm.type')"
            small-label
            required
          >
            <Dropdown v-model="values.type">
              <DropdownItem
                v-for="item in externalScriptTypes"
                :key="item.value"
                :name="item.name"
                :value="item.value"
              />
            </Dropdown>
          </FormGroup>
          <FormGroup
            :label="$t('customCodeSettingScriptForm.crossorigin')"
            small-label
            required
          >
            <Dropdown v-model="values.crossorigin">
              <DropdownItem
                v-for="item in crossoriginTypes"
                :key="item.value"
                :name="item.name"
                :value="item.value"
              />
            </Dropdown>
          </FormGroup>
          <FormGroup
            v-if="values.type === 'javascript'"
            :label="$t('customCodeSettingScriptForm.loadType')"
            small-label
            required
          >
            <Dropdown v-model="values.load_type">
              <DropdownItem
                v-for="item in externalScriptLoadTypes"
                :key="item.value"
                :name="item.name"
                :value="item.value"
              />
            </Dropdown>
          </FormGroup>
        </FormRow>
        <ButtonIcon
          type="secondary"
          icon="iconoir-bin"
          @click.prevent="$emit('delete')"
        />
      </div>
      <FormGroup
        small-label
        :label="$t('customCodeSettingScriptForm.url')"
        :error-message="getFirstErrorMessage('url')"
        required
      >
        <FormInput
          v-model="v$.values.url.$model"
          :placeholder="$t('customCodeSettingScriptForm.urlPlaceholder')"
        />
      </FormGroup>
    </div>
  </div>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import { helpers } from '@vuelidate/validators'

import form from '@baserow/modules/core/mixins/form'
import { isValidAbsoluteURL } from '@baserow/modules/core/utils/string'

import {
  EXTERNAL_SCRIPT_TYPES,
  EXTERNAL_SCRIPT_LOAD_TYPES,
  EXTERNAL_SCRIPT_CROSSORIGIN_TYPES,
} from '@baserow_enterprise/builder/enums'

export default {
  name: 'CustomCodeSettingScriptForm',
  mixins: [form],
  setup() {
    return { v$: useVuelidate({ lazy: true }) }
  },
  data() {
    return {
      values: { type: '', url: '', load_type: '', crossorigin: false },
      allowedValues: ['type', 'url', 'load_type', 'crossorigin'],
    }
  },
  computed: {
    externalScriptTypes() {
      return [
        {
          name: this.$t('customCodeSettingScriptForm.typeCSS'),
          value: EXTERNAL_SCRIPT_TYPES.STYLESHEET,
        },
        {
          name: this.$t('customCodeSettingScriptForm.typeJS'),
          value: EXTERNAL_SCRIPT_TYPES.JAVASCRIPT,
        },
      ]
    },
    externalScriptLoadTypes() {
      return [
        {
          name: this.$t('customCodeSettingScriptForm.loadTypeNone'),
          value: EXTERNAL_SCRIPT_LOAD_TYPES.NONE,
        },
        {
          name: this.$t('customCodeSettingScriptForm.loadTypeDefer'),
          value: EXTERNAL_SCRIPT_LOAD_TYPES.DEFER,
        },
        {
          name: this.$t('customCodeSettingScriptForm.loadTypeAsync'),
          value: EXTERNAL_SCRIPT_LOAD_TYPES.ASYNC,
        },
      ]
    },
    crossoriginTypes() {
      return [
        {
          name: this.$t('customCodeSettingScriptForm.crossoriginTypeNone'),
          value: EXTERNAL_SCRIPT_CROSSORIGIN_TYPES.NONE,
        },
        {
          name: this.$t('customCodeSettingScriptForm.crossoriginTypeAnonymous'),
          value: EXTERNAL_SCRIPT_CROSSORIGIN_TYPES.ANONYMOUS,
        },
        {
          name: this.$t(
            'customCodeSettingScriptForm.crossoriginTypeCredentials'
          ),
          value: EXTERNAL_SCRIPT_CROSSORIGIN_TYPES.CREDENTIALS,
        },
      ]
    },
  },
  validations() {
    return {
      values: {
        url: {
          isValidAbsoluteURL: helpers.withMessage(
            this.$t('error.invalidURL'),
            (v) => !v || isValidAbsoluteURL(v)
          ),
        },
      },
    }
  },
}
</script>
