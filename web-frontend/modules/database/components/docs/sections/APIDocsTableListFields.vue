<template>
  <div class="api-docs__item">
    <div class="api-docs__left">
      <h3
        :id="`section-table-${table.id}-field-list`"
        class="api-docs__heading-3"
      >
        {{ $t('apiDocs.listFields') }}
      </h3>
      <MarkdownIt :content="$t('apiDocsTableListFields.description', table)" />
      <h4 class="api-docs__heading-4">
        {{ $t('apiDocsTableListFields.resultFieldProperties') }}
      </h4>
      <ul class="api-docs__parameters">
        <APIDocsParameter name="id" :optional="false" type="integer">
          <MarkdownIt :content="$t('apiDocsTableListFields.id')" />
        </APIDocsParameter>
        <APIDocsParameter name="name" :optional="false" type="string">
          {{ $t('apiDocsTableListFields.name') }}
        </APIDocsParameter>
        <APIDocsParameter name="table_id" :optional="false" type="integer">
          {{ $t('apiDocsTableListFields.tableId') }}
        </APIDocsParameter>
        <APIDocsParameter name="order" :optional="false" type="integer">
          {{ $t('apiDocsTableListFields.order') }}
        </APIDocsParameter>
        <APIDocsParameter name="primary" :optional="false" type="boolean">
          <MarkdownIt :content="$t('apiDocsTableListFields.primary')" />
        </APIDocsParameter>
        <APIDocsParameter name="type" :optional="false" type="string">
          {{ $t('apiDocsTableListFields.type') }}
        </APIDocsParameter>
        <APIDocsParameter name="read_only" :optional="false" type="boolean">
          {{ $t('apiDocsTableListFields.readOnly') }}
        </APIDocsParameter>
        <APIDocsParameter name="description" :optional="false" type="string">
          {{ $t('apiDocsTableListFields.descriptionField') }}
        </APIDocsParameter>
      </ul>
      <p class="api-docs__content">
        {{ $t('apiDocsTableListFields.extraProps') }}
      </p>
    </div>
    <div class="api-docs__right">
      <APIDocsExample
        :value="value"
        type="GET"
        :url="getFieldsURL(table)"
        :response="getResponseFields(table)"
        :include-user-fields-checkbox="false"
        @input="$emit('input', $event)"
      ></APIDocsExample>
    </div>
  </div>
</template>

<script>
import APIDocsExample from '@baserow/modules/database/components/docs/APIDocsExample'
import APIDocsParameter from '@baserow/modules/database/components/docs/APIDocsParameter'

export default {
  name: 'APIDocsTableListFields',
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
    fields: { type: Object, required: true },
  },
  emits: ['input'],
  methods: {
    getFieldsURL(table) {
      return `${this.$config.public.publicBackendUrl}/api/database/fields/table/${table.id}/`
    },
    /**
     * Generates a sample field list response based on the available fields of the table.
     */
    getResponseFields(table) {
      return this.fields[table.id]
        .slice(0, 3)
        .map(({ _: { fieldResponseExample } }) => fieldResponseExample)
    },
  },
}
</script>
