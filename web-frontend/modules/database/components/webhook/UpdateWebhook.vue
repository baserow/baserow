<template>
  <div>
    <Error :error="error" />
    <WebhookForm
      ref="form"
      :database="database"
      :table="table"
      :fields="fields"
      :views="views"
      :default-values="webhook"
      @submitted="submit"
      @formchange="handleFormChange"
    >
      <div class="actions">
        <Button tag="a" type="danger" @click="$refs.deleteWebhookModal.show()">
          {{ $t('action.delete') }}
        </Button>
        <div class="align-right">
          <p v-if="saved">
            <strong class="color-success">{{
              $t('webhook.successfullyUpdated')
            }}</strong>
          </p>
          <Button
            v-if="!saved"
            type="primary"
            :loading="loading"
            :disabled="loading"
          >
            {{ $t('action.save') }}
          </Button>
        </div>
      </div>
      <DeleteWebhookModal
        ref="deleteWebhookModal"
        :webhook="webhook"
        @deleted="$emit('deleted', $event)"
      />
    </WebhookForm>
  </div>
</template>

<script>
import error from '@baserow/modules/core/mixins/error'
import WebhookForm from '@baserow/modules/database/components/webhook/WebhookForm'
import DeleteWebhookModal from '@baserow/modules/database/components/webhook/DeleteWebhookModal'
import WebhookService from '@baserow/modules/database/services/webhook'

const {
  ResponseErrorMessage,
} = require('@baserow/modules/core/plugins/clientHandler')

export default {
  name: 'UpdateWebhook',
  components: { WebhookForm, DeleteWebhookModal },
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
    webhook: {
      type: Object,
      required: true,
    },
  },
  data() {
    return {
      loading: false,
      saved: false,
    }
  },
  methods: {
    handleFormChange() {
      this.saved = false
    },
    async submit(values) {
      this.hideError()
      this.loading = true

      try {
        const { data } = await WebhookService(this.$client).update(
          this.webhook.id,
          values
        )
        this.saved = true
        this.$emit('updated', data)

        setTimeout(() => {
          this.saved = false
        }, 5000)
      } catch (error) {
        this.handleError(error, 'webhook', null, {
          url: {
            invalid_url: new ResponseErrorMessage(
              this.$t('webhook.form.invalidURLTitle'),
              this.$t('webhook.form.invalidURLDescription')
            ),
          },
        })
      }

      this.loading = false
    },
  },
}
</script>
