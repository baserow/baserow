<template>
  <Modal ref="modal" :can-close="!loading">
    <h2 class="box__title">{{ $t('untrustedContentReviewModal.title') }}</h2>
    <Error :error="error" />
    <p>{{ $t('untrustedContentReviewModal.description') }}</p>
    <h3 class="untrusted-content-report__heading">
      {{ $t('untrustedContentReviewModal.contents') }}
    </h3>
    <ul v-if="report.length" class="untrusted-content-report">
      <li
        v-for="(item, index) in report"
        :key="index"
        class="untrusted-content-report__item"
      >
        <i
          class="untrusted-content-report__icon"
          :class="typeDetails[item.type]?.icon || 'iconoir-code'"
          aria-hidden="true"
        />
        <div class="untrusted-content-report__body">
          <div class="untrusted-content-report__title">
            {{
              $t(
                typeLabels[item.type] ||
                  'untrustedContentReviewModal.typeUnknown'
              )
            }}
            <span v-if="item.label"> — {{ item.label }}</span>
          </div>
          <div v-if="item.page_name" class="untrusted-content-report__detail">
            {{
              $t('untrustedContentReviewModal.page', { name: item.page_name })
            }}
          </div>
          <div v-if="item.url" class="untrusted-content-report__detail">
            {{ item.url }}
          </div>
          <p class="untrusted-content-report__risk">
            {{
              $t(
                typeDetails[item.type]?.risk ||
                  'untrustedContentReviewModal.riskUnknown'
              )
            }}
          </p>
        </div>
      </li>
    </ul>
    <p v-else>{{ $t('untrustedContentReviewModal.empty') }}</p>
    <Alert type="warning">
      {{ $t('untrustedContentReviewModal.confirmation') }}
    </Alert>
    <div class="actions actions--right actions--gap margin-bottom-0">
      <Button type="secondary" :disabled="loading" @click="modal.hide()">{{
        $t('action.cancel')
      }}</Button>
      <Button v-if="canTrust" :loading="loading" @click="trust">
        {{ $t('untrustedContentReviewModal.trust') }}
      </Button>
    </div>
  </Modal>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import Modal from '@baserow/modules/core/components/Modal'
import Alert from '@baserow/modules/core/components/Alert'

const props = defineProps({
  report: { type: Array, default: () => [] },
  canTrust: { type: Boolean, default: false },
  trustContent: { type: Function, required: true },
})
const { t } = useI18n()
const modal = ref(null)
const loading = ref(false)
const error = reactive({ visible: false, title: '', message: '' })
const typeLabels = {
  iframe: 'untrustedContentReviewModal.typeIframe',
  builder_code_action: 'untrustedContentReviewModal.typeCodeAction',
  automation_code_node: 'untrustedContentReviewModal.typeCodeNode',
  custom_css: 'untrustedContentReviewModal.typeCss',
  custom_js: 'untrustedContentReviewModal.typeJs',
  external_script: 'untrustedContentReviewModal.typeScript',
  external_stylesheet: 'untrustedContentReviewModal.typeStylesheet',
}

const typeDetails = {
  iframe: {
    icon: 'iconoir-internet',
    risk: 'untrustedContentReviewModal.riskIframe',
  },
  builder_code_action: {
    icon: 'iconoir-code',
    risk: 'untrustedContentReviewModal.riskCode',
  },
  automation_code_node: {
    icon: 'iconoir-code',
    risk: 'untrustedContentReviewModal.riskCode',
  },
  custom_css: {
    icon: 'iconoir-design-pencil',
    risk: 'untrustedContentReviewModal.riskStyles',
  },
  custom_js: {
    icon: 'iconoir-code',
    risk: 'untrustedContentReviewModal.riskScript',
  },
  external_script: {
    icon: 'iconoir-code',
    risk: 'untrustedContentReviewModal.riskScript',
  },
  external_stylesheet: {
    icon: 'iconoir-design-pencil',
    risk: 'untrustedContentReviewModal.riskStyles',
  },
}

/** Enable content only after the user confirms, keeping failures in the modal. */
const trust = async () => {
  if (!props.canTrust || loading.value) return
  error.visible = false
  loading.value = true
  try {
    await props.trustContent()
    modal.value?.hide()
  } catch (caught) {
    error.title = t('untrustedContentReviewModal.errorTitle')
    error.message = t('untrustedContentReviewModal.errorMessage')
    error.visible = true
    caught.handler?.handled()
  } finally {
    loading.value = false
  }
}
const show = () => {
  error.visible = false
  modal.value.show()
}
defineExpose({ show })
</script>
