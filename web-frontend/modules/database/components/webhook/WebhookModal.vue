<template>
  <Modal @hidden="$emit('hidden')">
    <h2 class="box__title">
      {{ $t('webhookModal.title', { name: table.name }) }}
    </h2>
    <Error :error="error"></Error>
    <div v-if="loading" class="loading"></div>
    <template v-else-if="!error.visible">
      <div class="align-right">
        <a v-if="state === 'list'" class="button" @click="state = 'create'">
          {{ $t('webhookModal.createWebhook') }}
          <i class="iconoir-plus"></i>
        </a>
        <a v-if="state === 'create'" class="button" @click="state = 'list'">
          <i class="iconoir-arrow-left"></i>
          {{ $t('webhookModal.backToList') }}
        </a>
      </div>
      <WebhookList
        v-if="state === 'list'"
        :database="database"
        :table="table"
        :fields="tableFields"
        :views="tableViews"
        :webhooks="webhooks"
        @updated="updated"
        @deleted="deleted"
      />
      <CreateWebhook
        v-else-if="state === 'create'"
        :database="database"
        :table="table"
        :fields="tableFields"
        :views="tableViews"
        @created="created"
      />
    </template>
  </Modal>
</template>

<script>
import modal from '@baserow/modules/core/mixins/modal'
import error from '@baserow/modules/core/mixins/error'
import WebhookList from '@baserow/modules/database/components/webhook/WebhookList'
import CreateWebhook from '@baserow/modules/database/components/webhook/CreateWebhook'
import WebhookService from '@baserow/modules/database/services/webhook'
import FieldService from '@baserow/modules/database/services/field'
import ViewService from '@baserow/modules/database/services/view'

export default {
  name: 'WebhookModal',
  components: {
    CreateWebhook,
    WebhookList,
  },
  mixins: [modal, error],
  props: {
    database: {
      type: Object,
      required: true,
    },
    table: {
      type: Object,
      required: true,
    },
    fields: {
      type: [Array, null],
      required: false,
      default: null,
    },
    views: {
      type: [Array, null],
      required: false,
      default: null,
    },
  },
  data() {
    return {
      loading: false,
      state: 'list',
      webhooks: [],
      tableFields: [],
      tableViews: [],
    }
  },
  methods: {
    show(...args) {
      this.getRootModal().show(...args)
      this.hideError()
      this.fetchInitial()
    },
    async fetchInitial() {
      this.loading = true

      try {
        const { data } = await WebhookService(this.$client).fetchAll(
          this.table.id
        )
        this.webhooks = data
      } catch (e) {
        this.handleError(e)
      }

      const selectedTableId = this.$store.getters['table/getSelected']?.id
      const isSelectedTable =
        selectedTableId && selectedTableId === this.table.id
      // The parent component can provide the fields, but if it doesn't we need to
      // fetch them ourselves. If the table is the selected one, we can use the
      // store, otherwise we need to fetch them.
      if (Array.isArray(this.fields)) {
        this.tableFields = this.fields
      } else if (isSelectedTable) {
        this.tableFields = this.$store.getters['field/getAll']
      } else {
        const { data: fields } = await FieldService(this.$client).fetchAll(
          this.table.id
        )
        this.tableFields = fields
      }

      // The parent component can provide the views, but if it doesn't we need to
      // fetch them ourselves. If the table is the selected one, we can use the
      // store, otherwise we need to fetch them.
      if (Array.isArray(this.views)) {
        this.tableViews = this.views
      } else if (isSelectedTable) {
        this.tableViews = this.$store.getters['view/getAll']
      } else {
        const { data: views } = await ViewService(this.$client).fetchAll(
          this.table.id
        )
        this.tableViews = views
      }

      this.loading = false
    },
    created(webhook) {
      this.webhooks.push(webhook)
      this.state = 'list'
    },
    updated(webhook) {
      const index = this.webhooks.findIndex((w) => w.id === webhook.id)
      if (index > -1) {
        Object.assign(this.webhooks[index], webhook)
      }
    },
    deleted(webhook) {
      const index = this.webhooks.findIndex((w) => w.id === webhook.id)
      if (index > -1) {
        this.webhooks.splice(index, 1)
      }
    },
  },
}
</script>
