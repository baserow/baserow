<template>
  <div class="layout__col-2-scroll">
    <div class="admin-health">
      <h1>
        {{ $t('health.title') }}
      </h1>
      <div class="admin-health__group">
        <div class="admin-health__description">
          {{ $t('health.description') }}
        </div>
        <div>
          <div
            v-for="(status, checkName) in healthChecks"
            :key="checkName"
            class="admin-health__check-item"
          >
            <div class="admin-health__check-item-label">
              <div class="admin-health__check-item-name">
                {{ camelCaseToSpaceSeparated(checkName) }}
              </div>
            </div>
            <div
              class="admin-health__icon"
              :class="status !== 'working' ? 'warning' : ''"
            >
              <i
                :class="
                  status === 'working'
                    ? 'iconoir-check admin-health__icon--success'
                    : 'iconoir-cancel admin-health__icon--fail'
                "
              ></i>
              <div
                v-if="status !== 'working'"
                class="admin-health__check-item-description"
              >
                {{ status }}
              </div>
            </div>
          </div>
          <div class="admin-health__check-item">
            <div class="admin-health__check-item-label">
              <div class="admin-health__check-item-name">Celery queue size</div>
            </div>
            {{ celeryQueueSize }}
          </div>
          <div class="admin-health__check-item">
            <div class="admin-health__check-item-label">
              <div class="admin-health__check-item-name">
                Celery export queue size
              </div>
            </div>
            {{ celeryExportQueueSize }}
          </div>
        </div>
      </div>
      <div class="admin-health__group">
        <EmailTester></EmailTester>
      </div>
      <div class="admin-health__group">
        <h2>Error tester</h2>
        <Button @click="error()">Click to throw error</Button>
      </div>
    </div>
  </div>
</template>

<script>
import HealthService from '@baserow/modules/core/services/health'
import EmailTester from '@baserow/modules/core/components/health/EmailTester.vue'

export default {
  components: { EmailTester },
  layout: 'app',
  middleware: 'staff',
  async asyncData({ app }) {
    const { data } = await HealthService(app.$client).getAll()
    return {
      healthChecks: data.checks,
      celeryQueueSize: data.celery_queue_size,
      celeryExportQueueSize: data.celery_export_queue_size,
    }
  },
  methods: {
    camelCaseToSpaceSeparated(camelCaseString) {
      if (!camelCaseString) {
        return 'unknown'
      } else {
        camelCaseString = camelCaseString.toString()
      }
      return camelCaseString.replace(/([A-Z])/g, ' $1')
    },
    error() {
      setTimeout(() => {
        throw new Error('Health check error')
      }, 1)
    },
  },
}
</script>
