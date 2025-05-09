<template>
  <div class="api-docs__item">
    <div class="api-docs__left">
      <div class="api-docs__heading-wrapper">
        <h3 :id="'section-list-tables'" class="api-docs__heading-3">
          <span>
            {{ $t('apiDocsListTables.listTables') }}
          </span>
        </h3>
        <div class="api-docs__endpoint-type"></div>
      </div>

      <MarkdownIt
        class="api-docs__content"
        :content="$t('apiDocsListTables.listTablesDescription')"
      />
    </div>

    <div class="api-docs__right">
      <APIDocsExample
        :value="value"
        type="GET"
        :url="getListTablesUrl()"
        :response="getListTablesResponse()"
        :include-user-fields-checkbox="false"
        @input="$emit('input', $event)"
      ></APIDocsExample>
    </div>
  </div>
</template>

<script>
import APIDocsExample from '@baserow/modules/database/components/docs/APIDocsExample'

export default {
  name: 'APIDocsListTables',
  components: {
    APIDocsExample,
  },
  props: {
    value: {
      type: Object,
      required: true,
    },
  },
  methods: {
    getListTablesResponse() {
      return [
        {
          id: 0,
          name: 'string',
          order: 2147483647,
          database_id: 0,
        },
      ]
    },
    getListTablesUrl() {
      return (
        this.$config.PUBLIC_BACKEND_URL + '/api/database/tables/all-tables/'
      )
    },
  },
}
</script>
