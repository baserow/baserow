<template>
  <div>
    <Checkbox v-model="values.allow_endpoint_authentication">
      {{ $t('fieldPasswordSubForm.allowEndpointAuthentication') }}
      <HelpIcon
        class="margin-left-1"
        :tooltip-content-classes="[
          'tooltip__content--expandable',
          'tooltip__content--expandable-plain-text',
        ]"
        :tooltip="$t('fieldPasswordSubForm.allowEndpointAuthenticationHelp')"
      />
    </Checkbox>
    <div
      v-if="defaultValues.id && values.allow_endpoint_authentication"
      class="margin-top-1"
    >
      <nuxt-link
        :to="{
          name: 'database-api-docs-detail',
          params: { databaseId: table.database_id },
          hash:
            '#section-password-field-' + defaultValues.id + '-authentication',
        }"
        >Open API documentation</nuxt-link
      >
    </div>
    <p style="width: 366px; white-space: initial">
      {{ $t('fieldPasswordSubForm.description') }}
    </p>
  </div>
</template>

<script>
import form from '@baserow/modules/core/mixins/form'
import fieldSubForm from '@baserow/modules/database/mixins/fieldSubForm'

export default {
  name: 'FieldPasswordSubForm',
  mixins: [form, fieldSubForm],
  data() {
    return {
      allowedValues: ['allow_endpoint_authentication'],
      values: {
        allow_endpoint_authentication: false,
      },
    }
  },
}
</script>
