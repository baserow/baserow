<template>
  <div class="api-docs__item">
    <div class="api-docs__left">
      <h3
        :id="'section-table-' + table.id + '-move'"
        class="api-docs__heading-3"
      >
        {{ $t('apiDocs.moveRow') }}
      </h3>
      <MarkdownIt
        class="api-docs__content"
        :content="$t('apiDocsTableMoveRow.description', table)"
      />
      <h4 class="api-docs__heading-4">{{ $t('apiDocs.pathParameters') }}</h4>
      <ul class="api-docs__parameters">
        <APIDocsParameter name="row_id" type="integer">
          {{ $t('apiDocsTableMoveRow.rowId') }}
        </APIDocsParameter>
      </ul>
      <h4 class="api-docs__heading-4">{{ $t('apiDocs.queryParameters') }}</h4>
      <ul class="api-docs__parameters">
        <APIDocsParameter name="user_field_names" :optional="true" type="any">
          <MarkdownIt
            class="api-docs__content"
            :content="$t('apiDocs.userFieldNamesDescription')"
          />
        </APIDocsParameter>
        <APIDocsParameter name="before_id" type="integer" :optional="true">
          {{ $t('apiDocsTableMoveRow.before') }}
        </APIDocsParameter>
        <APIDocsParameter
          name="send_webhook_events"
          :optional="true"
          type="any"
        >
          <MarkdownIt
            class="api-docs__content"
            :content="$t('apiDocs.sendWebhookEventsDescription')"
          />
        </APIDocsParameter>
      </ul>
    </div>
    <div class="api-docs__right">
      <APIDocsExample
        :value="value"
        type="PATCH"
        :url="getItemUrl(table, false) + 'move/' + userFieldNamesParam"
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
  name: 'APIDocsTableMoveRow',
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
  computed: {
    userFieldNamesParam() {
      return this.userFieldNames ? '?user_field_names=true' : ''
    },
  },
  methods: {},
}
</script>
