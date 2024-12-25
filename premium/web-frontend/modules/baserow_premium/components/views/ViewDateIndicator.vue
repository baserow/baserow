<template>
  <div class="view-date-indicator">{{ formattedDate }}</div>
</template>

<script>
import { mapGetters } from 'vuex'
import moment from 'moment'

export default {
  name: 'ViewDateIndicator',
  props: {
    date: {
      type: Object, // a moment object
      required: true,
    },
    format: {
      type: String,
      default: 'MMMM YYYY',
    },
  },
  data() {
    return {
      formattedDate: '',
    }
  },
  computed: {
    ...mapGetters({
      language: 'auth/getLanguage',
    }),
  },
  watch: {
    date: {
      handler() {
        this.updateFormattedDate()
      },
      immediate: true,
    },
    language() {
      this.updateFormattedDate()
    },
  },
  methods: {
    updateFormattedDate() {
      this.formattedDate = moment(this.date)
        .locale(this.language)
        .format(this.format)
    },
  },
}
</script>
