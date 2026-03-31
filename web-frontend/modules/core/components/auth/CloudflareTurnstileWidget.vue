<template>
  <div ref="container"></div>
</template>

<script>
const TURNSTILE_SCRIPT_URL =
  'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit'

let turnstileScriptLoaded = false
let turnstileScriptLoading = false
const turnstileLoadCallbacks = []

function loadTurnstileScript() {
  return new Promise((resolve, reject) => {
    if (turnstileScriptLoaded && window.turnstile) {
      resolve()
      return
    }

    turnstileLoadCallbacks.push({ resolve, reject })

    if (turnstileScriptLoading) {
      return
    }

    turnstileScriptLoading = true
    const script = document.createElement('script')
    script.src = TURNSTILE_SCRIPT_URL
    script.async = true
    script.defer = true
    script.onload = () => {
      turnstileScriptLoaded = true
      turnstileScriptLoading = false
      turnstileLoadCallbacks.forEach((cb) => cb.resolve())
      turnstileLoadCallbacks.length = 0
    }
    script.onerror = () => {
      turnstileScriptLoading = false
      const error = new Error('Failed to load Turnstile script')
      turnstileLoadCallbacks.forEach((cb) => cb.reject(error))
      turnstileLoadCallbacks.length = 0
    }
    document.head.appendChild(script)
  })
}

export default {
  name: 'CloudflareTurnstileWidget',
  props: {
    captchaSettings: {
      type: Object,
      required: true,
    },
  },
  emits: ['token'],
  data() {
    return {
      widgetId: null,
    }
  },
  async mounted() {
    try {
      await loadTurnstileScript()
    } catch {
      this.$emit('token', '')
      return
    }

    await this.$nextTick()

    if (!this.$refs.container) {
      return
    }

    this.widgetId = window.turnstile.render(this.$refs.container, {
      sitekey: this.captchaSettings.site_key,
      callback: (token) => {
        this.$emit('token', token)
      },
      'expired-callback': () => {
        this.$emit('token', '')
      },
      'error-callback': () => {
        this.$emit('token', '')
      },
    })
  },
  beforeUnmount() {
    if (this.widgetId != null && window.turnstile) {
      window.turnstile.remove(this.widgetId)
      this.widgetId = null
    }
  },
  methods: {
    reset() {
      if (this.widgetId != null && window.turnstile) {
        window.turnstile.reset(this.widgetId)
      }
      this.$emit('token', '')
    },
  },
}
</script>
