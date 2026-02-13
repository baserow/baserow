<template>
  <div class="api-docs__item">
    <div class="api-docs__left">
      <h3
        :id="'section-table-' + table.id + '-get'"
        class="api-docs__heading-3"
      >
        {{ $t('apiDocs.getRow') }}
      </h3>
      <p class="api-docs__content">
        {{ $t('apiDocsTableGetRow.description', table) }}
      </p>
      <h4 class="api-docs__heading-4">
        {{ $t('apiDocs.pathParameters') }}
      </h4>
      <ul class="api-docs__parameters">
        <APIDocsParameter name="row_id" type="integer">
          {{ $t('apiDocsTableGetRow.rowId') }}
        </APIDocsParameter>
      </ul>
      <h4 class="api-docs__heading-4">
        {{ $t('apiDocs.queryParameters') }}
      </h4>
      <ul class="api-docs__parameters">
        <APIDocsParameter name="user_field_names" :optional="true" type="any">
          <MarkdownIt
            class="api-docs__content"
            :content="$t('apiDocs.userFieldNamesDescription')"
          />
        </APIDocsParameter>
      </ul>
    </div>
    <div class="api-docs__right">
      <APIDocsExample
        :value="value"
        type="GET"
        :url="getItemUrl(table, true)"
        :response="getResponseItem(table)"
        :mapping="getFieldMapping(table)"
        @input="$emit('input', $event)"
      ></APIDocsExample>
    </div>
  </div>
</template>

<script>
import APIDocsExample from '@baserow/modules/database/components/docs/APIDocsExample'
import APIDocsParameter from '@baserow/modules/database/components/docs/APIDocsParameter'

export default {
  name: 'APIDocsTableGetRow',
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
    getItemUrl: { type: Function, required: true },
    getResponseItem: { type: Function, required: true },
    getFieldMapping: { type: Function, required: true },
  },
  emits: ['input'],
  methods: {},
}
</script>
