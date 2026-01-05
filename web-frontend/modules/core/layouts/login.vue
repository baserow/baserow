<template>
  <div>
    <Toasts></Toasts>
    <div class="auth__container">
      <slot />
    </div>
  </div>
</template>

<script>
import { useHead } from '#imports'
import Toasts from '@baserow/modules/core/components/toasts/Toasts'

export default {
  components: { Toasts },
  setup() {
    useHead({
      bodyAttrs: { class: 'auth__body' },
    })
  },
}
</script>
