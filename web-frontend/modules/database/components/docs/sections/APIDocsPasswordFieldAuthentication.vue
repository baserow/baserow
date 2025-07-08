<template>
  <div class="api-docs__item">
    <div class="api-docs__left">
      <h3
        :id="'section-password-field-' + field.id + '-authentication'"
        class="api-docs__heading-3"
      >
        {{
          $t('apiDocsPasswordFieldAuthentication.title', { name: field.name })
        }}
      </h3>
      <MarkdownIt
        class="api-docs__content"
        :content="
          $t('apiDocsPasswordFieldAuthentication.description', {
            name: field.name,
          })
        "
      />
      <h4 class="api-docs__heading-4">{{ $t('apiDocs.requestBodySchema') }}</h4>
      <ul class="api-docs__parameters">
        <APIDocsParameter name="field_id" :optional="false" type="integer">
          {{ $t('apiDocsPasswordFieldAuthentication.fieldId') }}
        </APIDocsParameter>
        <APIDocsParameter name="row_id" :optional="false" type="integer">
          {{ $t('apiDocsPasswordFieldAuthentication.rowId') }}
        </APIDocsParameter>
        <APIDocsParameter name="password" :optional="false" type="string">
          {{ $t('apiDocsPasswordFieldAuthentication.password') }}
        </APIDocsParameter>
      </ul>
    </div>
    <div class="api-docs__right">
      <APIDocsExample
        :value="value"
        type="POST"
        :url="
          $config.PUBLIC_BACKEND_URL +
          `/api/database/fields/password-authentication/`
        "
        :request="{ field_id: 1, row_id: 1, password: 'password' }"
        :response="{ is_correct: true }"
        @input="$emit('input', $event)"
      ></APIDocsExample>
    </div>
  </div>
</template>

<script>
import APIDocsExample from '@baserow/modules/database/components/docs/APIDocsExample'
import APIDocsParameter from '@baserow/modules/database/components/docs/APIDocsParameter'

export default {
  name: 'APIDocsTablePasswordFieldAuthentication',
  components: {
    APIDocsParameter,
    APIDocsExample,
  },
  props: {
    value: {
      type: Object,
      required: true,
    },
    table: { type: Object, required: true },
    field: { type: Object, required: true },
  },
  methods: {},
}
</script>
