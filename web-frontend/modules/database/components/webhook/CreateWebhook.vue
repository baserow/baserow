<template>
  <div>
    <Error :error="error" />
    <WebhookForm
      ref="form"
      :database="database"
      :table="table"
      :fields="fields"
      :views="views"
      @submitted="submit"
    >
      <div class="actions">
        <div class="align-right">
          <Button type="primary" :loading="loading" :disabled="loading">
            {{ $t('action.save') }}
          </Button>
        </div>
      </div>
    </WebhookForm>
  </div>
</template>

<script>
import error from '@baserow/modules/core/mixins/error'
import { ResponseErrorMessage } from '@baserow/modules/core/plugins/clientHandler'
import WebhookForm from '@baserow/modules/database/components/webhook/WebhookForm'
import WebhookService from '@baserow/modules/database/services/webhook'

export default {
  name: 'CreateWebhook',
  components: { WebhookForm },
  mixins: [error],
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
      type: Array,
      required: true,
    },
    views: {
      type: Array,
      required: true,
    },
  },
  data() {
    return {
      loading: false,
    }
  },
  methods: {
    async submit(values) {
      this.loading = true

      try {
        const { data } = await WebhookService(this.$client).create(
          this.table.id,
          values
        )
        this.$emit('created', data)
      } catch (error) {
        this.handleError(
          error,
          'webhook',
          {
            ERROR_TABLE_WEBHOOK_MAX_LIMIT_EXCEEDED: new ResponseErrorMessage(
              this.$t('createWebhook.errorTableWebhookMaxLimitExceededTitle'),
              this.$t(
                'createWebhook.errorTableWebhookMaxLimitExceededDescription'
              )
            ),
          },
          {
            url: {
              invalid_url: new ResponseErrorMessage(
                this.$t('webhook.form.invalidURLTitle'),
                this.$t('webhook.form.invalidURLDescription')
              ),
            },
          }
        )
      }

      this.loading = false
    },
  },
}
</script>
