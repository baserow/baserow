<template>
  <form @submit.prevent @keydown.enter.stop>
    <h2 class="box__title">
      {{ $t('customCodeSettingForm.customCodeTitle') }}
    </h2>
    <p>
      {{ $t('customCodeSettingForm.customCodeHelp') }}
    </p>
    <FormGroup
      :label="$t('customCodeSettingForm.customCSS')"
      class="margin-bottom-2"
      small-label
      required
    >
      <CodeEditor
        v-model="values.custom_code.css"
        language="css"
        :placeholder="$t('customCodeSettingForm.customCSSPlaceholder')"
      />
    </FormGroup>
    <FormGroup
      :label="$t('customCodeSettingForm.customJS')"
      class="margin-bottom-2"
      small-label
      required
    >
      <CodeEditor
        v-model="values.custom_code.js"
        language="javascript"
        :placeholder="$t('customCodeSettingForm.customJSPlaceholder')"
      />
    </FormGroup>
    <hr class="margin-top-3 margin-bottom-3" />
    <div class="custom-code__add-script">
      <ButtonText
        type="secondary"
        class="custom-code__add-script-button"
        icon="iconoir-plus"
        @click="addExternalScript"
      >
        {{ $t('customCodeSettingForm.addExternalScript') }}
      </ButtonText>
    </div>
    <FormGroup
      :label="$t('customCodeSettingForm.externalScripts')"
      required
      :helper-text="
        values.scripts.length === 0 ? $t('customCodeSettingForm.noScript') : ''
      "
      small-label
    >
      <CustomCodeSettingScriptForm
        v-for="script in values.scripts"
        :key="script.id"
        v-sortable="{
          id: script.id,
          update: orderScripts,
          handle: '[data-sortable-handle]',
        }"
        :default-values="script"
        @values-changed="updateScript(script, $event)"
        @delete="onDelete(script)"
      />
    </FormGroup>
  </form>
</template>

<script>
import form from '@baserow/modules/core/mixins/form'
import { useVuelidate } from '@vuelidate/core'
import { uuid } from '@baserow/modules/core/utils/string'
import CodeEditor from '@baserow/modules/core/components/CodeEditor.vue'

import CustomCodeSettingScriptForm from '@baserow_enterprise/components/builder/CustomCodeSettingScriptForm.vue'
import {
  EXTERNAL_SCRIPT_TYPES,
  EXTERNAL_SCRIPT_LOAD_TYPES,
  EXTERNAL_SCRIPT_CROSSORIGIN_TYPES,
} from '@baserow_enterprise/builder/enums'

export default {
  name: 'CustomCodeSettingForm',
  components: { CodeEditor, CustomCodeSettingScriptForm },
  mixins: [form],
  setup() {
    return { v$: useVuelidate({ lazy: true }) }
  },
  data() {
    return {
      values: { custom_code: { css: '', js: '' }, scripts: [] },
      allowedValues: ['custom_code', 'scripts'],
    }
  },
  methods: {
    addExternalScript() {
      this.values.scripts.push({
        id: uuid(),
        type: EXTERNAL_SCRIPT_TYPES.STYLESHEET,
        url: '',
        load_type: EXTERNAL_SCRIPT_LOAD_TYPES.NONE,
        crossorigin: EXTERNAL_SCRIPT_CROSSORIGIN_TYPES.NONE,
      })
    },
    updateScript(script, values) {
      this.values.scripts = this.values.scripts.map((s) => {
        if (s.id === script.id) {
          return { ...s, ...values }
        }
        return s
      })
    },
    onDelete(script) {
      this.values.scripts = this.values.scripts.filter(
        (s) => s.id !== script.id
      )
    },
    orderScripts(newOrder) {
      const fieldById = Object.fromEntries(
        this.values.scripts.map((s) => [s.id, s])
      )
      this.values.scripts = newOrder.map((sId) => fieldById[sId])
    },
  },
  validations() {
    return {}
  },
}
</script>
