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
        v-model="values.airtableUrl"
        :error="v$.values.airtableUrl.$error"
        :placeholder="$t('importFromAirtable.airtableShareLinkPaste')"
        size="large"
        @blur="v$.values.airtableUrl.$touch()"
        @input="
          $emit(
            'input',
            v$.values.airtableUrl.$invalid ? '' : values.airtableUrl
          )
        "
      ></FormInput>
      <template #error>
        {{ $t('importFromAirtable.linkError') }}
      </template>
    </FormGroup>
    <slot></slot>
  </form>
</template>

<script>
import form from '@baserow/modules/core/mixins/form'

export default {
  name: 'AirtableImportForm',
  mixins: [form],
  data() {
    return {
      values: {
        airtableUrl: '',
      },
    }
  },
  validations: {
    values: {
      airtableUrl: {
        valid(value) {
          const regex = /https:\/\/airtable.com\/[shr|app](.*)$/g
          return !!value.match(regex)
        },
      },
    },
  },
}
</script>
