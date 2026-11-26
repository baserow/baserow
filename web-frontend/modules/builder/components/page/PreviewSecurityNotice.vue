<template>
  <div ref="notice" class="preview-security-notice">
    <div class="preview-security-notice__summary">
      <i class="preview-security-notice__icon iconoir-warning-triangle" />
      <span>{{ $t('previewSecurityNotice.summary') }}</span>
      <button
        type="button"
        class="preview-security-notice__toggle"
        :aria-expanded="expanded"
        :aria-label="
          expanded
            ? $t('previewSecurityNotice.collapse')
            : $t('previewSecurityNotice.expand')
        "
        @click="expanded = !expanded"
      >
        <i
          :class="expanded ? 'iconoir-nav-arrow-up' : 'iconoir-nav-arrow-down'"
        />
      </button>
    </div>
    <p v-if="expanded" class="preview-security-notice__details">
      {{ $t('previewSecurityNotice.details') }}
      <a
        class="preview-security-notice__link"
        :href="DOCUMENTATION_URL"
        target="_blank"
        rel="noopener noreferrer"
        >{{ $t('previewSecurityNotice.learnMore') }}</a
      >
    </p>
  </div>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'

defineOptions({
  name: 'PreviewSecurityNotice',
})

const DOCUMENTATION_URL =
  'https://baserow.io/docs/installation%2Fconfiguration#backend-application-builder-configuration'

// The application's own fixed header sticks below the notice, not under it.
const HEIGHT_VARIABLE = '--preview-security-notice-height'

const expanded = ref(false)
const notice = ref(null)
let observer

onMounted(() => {
  const publishHeight = () =>
    document.documentElement.style.setProperty(
      HEIGHT_VARIABLE,
      `${notice.value.offsetHeight}px`
    )
  observer = new ResizeObserver(publishHeight)
  observer.observe(notice.value)
  publishHeight()
})

onBeforeUnmount(() => {
  observer?.disconnect()
  document.documentElement.style.removeProperty(HEIGHT_VARIABLE)
})
</script>
