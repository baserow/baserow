<template>
  <form @submit.prevent="submit">
    <p class="margin-bottom-2">
      {{ $t('importFromAirtable.airtableShareLinkDescription') }}
      <br /><br />
      {{ $t('importFromAirtable.airtableShareLinkBeta') }}
    </p>
    <FormGroup
      :label="$t('importFromAirtable.airtableShareLinkTitle')"
      :error="v$.values.airtableUrl.$error"
      small-label
      required
      class="margin-bottom-2"
    >
      <FormInput
        v-model="v$.values.airtableUrl.$model"
        :error="v$.values.airtableUrl.$error"
        :placeholder="$t('importFromAirtable.airtableShareLinkPaste')"
        size="large"
        @blur="v$.values.airtableUrl.$touch"
      ></FormInput>
      <template #error>
        {{ $t('importFromAirtable.linkError') }}
      </template>
    </FormGroup>
    <div class="margin-bottom-2">
      <Checkbox v-model="values.skipFiles">
        {{ $t('importFromAirtable.skipFiles') }}
        <HelpIcon
          :tooltip="$t('importFromAirtable.skipFilesHelper')"
          :tooltip-content-type="'plain'"
          :tooltip-content-classes="[
            'tooltip__content--expandable',
            'tooltip__content--expandable-plain-text',
          ]"
          :icon="'info-empty'"
        />
      </Checkbox>
    </div>
    <div class="margin-bottom-2">
      <Checkbox v-model="values.useSession">
        {{ $t('importFromAirtable.useSession') }}
        <HelpIcon
          :tooltip="$t('importFromAirtable.useSessionHelper')"
          :tooltip-content-type="'plain'"
          :tooltip-content-classes="[
            'tooltip__content--expandable',
            'tooltip__content--expandable-plain-text',
          ]"
          :icon="'info-empty'"
        />
      </Checkbox>
    </div>
    <div v-if="values.useSession" class="margin-bottom-2">
      <p class="margin-bottom-2">
        {{ $t('importFromAirtable.sessionDescription') }}
      </p>
      <FormGroup
        :label="$t('importFromAirtable.sessionLabel')"
        :error="v$.values.session.$error"
        small-label
        required
        class="margin-bottom-2"
      >
        <FormInput
          v-model="v$.values.session.$model"
          :error="v$.values.session.$error"
          placeholder="eyJzZXNz..."
          size="large"
          @blur="v$.values.session.$touch"
        ></FormInput>
      </FormGroup>
      <FormGroup
        :label="$t('importFromAirtable.sessionSignatureLabel')"
        :error="v$.values.sessionSignature.$error"
        small-label
        required
        class="margin-bottom-2"
      >
        <FormInput
          v-model="v$.values.sessionSignature.$model"
          :error="v$.values.session.$error"
          placeholder="OYncZ-Nz..."
          size="large"
          @blur="v$.values.sessionSignature.$touch"
        ></FormInput>
      </FormGroup>
    </div>
    <slot></slot>
  </form>
</template>

<script>
import form from '@baserow/modules/core/mixins/form'
import { useVuelidate } from '@vuelidate/core'
import { required } from '@vuelidate/validators'

export default {
  name: 'AirtableImportForm',
  mixins: [form],
  setup() {
    return { v$: useVuelidate({ $lazy: true }) }
  },
  data() {
    return {
      values: {
        airtableUrl: '',
        skipFiles: false,
        useSession: false,
        session: '',
        sessionSignature: '',
      },
    }
  },
  watch: {
    values: {
      handler(values) {
        this.$emit('input', values)
      },
      deep: true,
    },
  },
  validations() {
    const rules = {
      values: {
        airtableUrl: {
          required,
          valid(value) {
            const regex = /https:\/\/airtable.com\/[shr|app](.*)$/g
            return !!value.match(regex)
          },
        },
      },
    }

    if (this.values.useSession) {
      rules.values.session = { required }
      rules.values.sessionSignature = { required }
    }

    return rules
  },
}
</script>
