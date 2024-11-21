<template>
  <div>
    <Toasts></Toasts>
    <div class="auth__container">
      <nuxt />
    </div>
  </div>
</template>

<script>
import Toasts from '@baserow/modules/core/components/toasts/Toasts'

export default {
  components: { Toasts },
  middleware: ['settings', 'urlCheck'],
  head() {
    return {
      bodyAttrs: {
        class: 'auth__body',
      },
    }
  },
}
</script>
