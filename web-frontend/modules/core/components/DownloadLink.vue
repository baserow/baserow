<template>
  <a v-if="!downloadXHR" :href="href" target="_blank" :download="filename">
    <slot></slot>
  </a>
  <a
    v-else
    :href="`${url}`"
    target="_blank"
    :download="filename"
    :class="{ [loadingClass]: loading }"
    @click="onClick($event)"
  >
    <slot :loading="loading"></slot>
  </a>
</template>

<script>
export default {
  name: 'DownloadLink',
  props: {
    url: {
      type: String,
      required: true,
    },
    filename: {
      type: String,
      required: true,
    },
    onError: {
      type: Function,
      required: false,
      default: null,
    },
    loadingClass: {
      type: String,
      required: true,
    },
  },
  data() {
    return { loading: false }
  },
  computed: {
    downloadXHR() {
      return this.$config.DOWNLOAD_FILE_VIA_XHR === '1'
    },
    href() {
      // Add the filename to the query string
      const url = new URL(this.url)
      url.searchParams.set('dl', this.filename)
      return url.toString()
    },
  },
  methods: {
    async download() {
      this.loading = true
      // We are using fetch here to avoid extra header
      // as we need to add them to CORS later
      const response = await fetch(this.url, {
        // Needed to prevent chrome not sending the Origin header in the actual GET
        // request. Without this header S3 will not respond with will not respond with
        // the correct CORS headers
        cache: 'no-store',
      })
      const blob = await response.blob()
      const data = window.URL.createObjectURL(blob)

      this.loading = false

      // Create temporary anchor element to trigger the download
      const a = document.createElement('a')
      a.style = 'display: none'
      a.href = data
      a.target = '_blank'
      a.download = this.filename
      document.body.appendChild(a)
      a.onclick = (e) => {
        // prevent modal/whatever closing
        e.stopPropagation()
      }
      a.click()

      setTimeout(function () {
        // Remove the element
        document.body.removeChild(a)
        // Release resource on after triggering the download
        window.URL.revokeObjectURL(data)
      }, 500)
    },
    onClick(event) {
      if (this.downloadXHR) {
        event.preventDefault()
        this.download().catch((error) => {
          // In any case, to be sure the loading animation will not last
          this.loading = false
          if (this.onError) {
            this.onError(error)
          } else {
            throw error
          }
        })
      }
    },
  },
}
</script>
