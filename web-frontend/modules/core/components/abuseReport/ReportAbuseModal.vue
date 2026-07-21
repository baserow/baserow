<template>
  <Modal ref="modal" small>
    <template v-if="success">
      <h2 class="box__title">{{ $t('reportAbuseModal.successTitle') }}</h2>
      <p>{{ $t('reportAbuseModal.successDescription') }}</p>
      <div class="actions margin-bottom-0">
        <div class="align-right">
          <Button type="primary" size="large" @click="hide()">
            {{ $t('reportAbuseModal.close') }}
          </Button>
        </div>
      </div>
    </template>
    <template v-else>
      <h2 class="box__title">{{ $t('reportAbuseModal.title') }}</h2>
      <p>{{ $t('reportAbuseModal.description') }}</p>
      <Error :error="error"></Error>
      <ReportAbuseForm @submitted="submitted">
        <div class="actions">
          <div class="align-right">
            <Button
              type="primary"
              size="large"
              :loading="loading"
              :disabled="loading"
            >
              {{ $t('reportAbuseModal.submit') }}
            </Button>
          </div>
        </div>
      </ReportAbuseForm>
    </template>
  </Modal>
</template>

<script>
import modal from '@baserow/modules/core/mixins/modal'
import error from '@baserow/modules/core/mixins/error'
import AbuseReportService from '@baserow/modules/core/services/abuseReport'
import { ResponseErrorMessage } from '@baserow/modules/core/plugins/clientHandler'

import ReportAbuseForm from './ReportAbuseForm'

export default {
  name: 'ReportAbuseModal',
  components: { ReportAbuseForm },
  mixins: [modal, error],
  props: {
    resourceType: {
      type: String,
      required: true,
    },
    identifier: {
      type: String,
      required: true,
    },
    requestConfig: {
      type: Object,
      required: false,
      default: () => ({}),
    },
  },
  data() {
    return {
      loading: false,
      success: false,
    }
  },
  methods: {
    show(...args) {
      this.success = false
      this.hideError()
      return modal.methods.show.call(this, ...args)
    },
    async submitted(values) {
      this.loading = true
      this.hideError()

      try {
        await AbuseReportService(this.$client).report(
          {
            resourceType: this.resourceType,
            identifier: this.identifier,
            ...values,
          },
          this.requestConfig
        )
        this.success = true
      } catch (error) {
        this.handleError(error, 'abuseReport', {
          ERROR_ABUSE_REPORTING_DISABLED: new ResponseErrorMessage(
            this.$t('reportAbuseModal.reportingDisabledTitle'),
            this.$t('reportAbuseModal.reportingDisabledDescription')
          ),
        })
      } finally {
        this.loading = false
      }
    },
  },
}
</script>
