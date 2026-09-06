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
          <template v-if="loading">
            <div
              v-for="index in 8"
              :key="`skeleton-${index}`"
              class="skeleton admin-health__check-item"
              aria-hidden="true"
            >
              <div class="admin-health__check-item-label">
                <div class="admin-health__check-item-name">
                  <SkeletonBlock width="160px"></SkeletonBlock>
                </div>
              </div>
              <div class="admin-health__icon">
                <SkeletonBlock
                  width="18px"
                  height="18px"
                  shape="circle"
                ></SkeletonBlock>
              </div>
            </div>
          </template>
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
            <span v-skeleton="{ loading, width: '24px' }">{{
              celeryQueueSize
            }}</span>
          </div>
          <div class="admin-health__check-item">
            <div class="admin-health__check-item-label">
              <div class="admin-health__check-item-name">
                Celery export queue size
              </div>
            </div>
            <span v-skeleton="{ loading, width: '24px' }">{{
              celeryExportQueueSize
            }}</span>
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

<script setup>
import { computed } from 'vue'
import { useHead } from '#imports'
import HealthService from '@baserow/modules/core/services/health'
import EmailTester from '@baserow/modules/core/components/health/EmailTester.vue'

// Page meta
definePageMeta({
  layout: 'app',
  middleware: 'staff',
})

// Access Baserow client from Nuxt app
const { $client, $i18n } = useNuxtApp()

useHead({ title: $i18n.t('health.title') })

// Fetched without blocking the navigation, so the page immediately renders with
// a skeleton loading state.
// Named `fetchStatus` because the template already uses `status` for the state
// of a health check.
const { data, status: fetchStatus } = await useAsyncData(
  'health',
  async () => {
    const res = await HealthService($client).getAll()
    return res.data
  },
  { lazy: true, server: false }
)

const loading = computed(() => ['idle', 'pending'].includes(fetchStatus.value))

const healthChecks = computed(() => data.value?.checks ?? [])
const celeryQueueSize = computed(() => data.value?.celery_queue_size ?? 0)
const celeryExportQueueSize = computed(
  () => data.value?.celery_export_queue_size ?? 0
)

// Methods
function camelCaseToSpaceSeparated(str) {
  if (!str) return 'unknown'
  return str.toString().replace(/([A-Z])/g, ' $1')
}

function error() {
  setTimeout(() => {
    throw new Error('Health check error')
  }, 1)
}
</script>
