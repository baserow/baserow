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
import {
  downloadViaXhr,
  getDownloadHref,
} from '@baserow/modules/core/utils/download'

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
      return `${this.$config.public.downloadFileViaXhr}` === '1'
    },
    href() {
      return getDownloadHref(this.url, this.filename)
    },
  },
  methods: {
    async download() {
      this.loading = true
      try {
        await downloadViaXhr(this.url, this.filename)
      } finally {
        this.loading = false
      }
    },
    onClick(event) {
      if (this.downloadXHR) {
        event.preventDefault()
        this.download().catch((error) => {
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
