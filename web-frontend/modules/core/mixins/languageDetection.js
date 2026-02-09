/**
 * This mixin forces language detection based on the browser settings instead of the
 * language stored in the nuxt-i18n cookie.
 */
export default {
  data() {
    return {
      originalLanguageBeforeDetect: null,
    }
  },
  created() {
    this.originalLanguageBeforeDetect = this.$i18n.locale
    this.$i18n.locale = this.$i18n.getBrowserLocale()
  },
  beforeUnmount() {
    this.$i18n.locale = this.originalLanguageBeforeDetect
  },
}
