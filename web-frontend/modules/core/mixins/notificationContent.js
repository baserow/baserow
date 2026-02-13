import { notifyIf } from '@baserow/modules/core/utils/error'

export default {
  emits: ['click'],

  props: {
    workspace: {
      type: Object,
      required: true,
    },
    notification: {
      type: Object,
      required: true,
    },
  },
  computed: {
    route() {
      return this.$registry
        .get('notification', this.notification.type)
        .getRoute(this.notification.data)
    },
    sender() {
      return this.notification.sender?.first_name
    },
  },
  methods: {
    markAsReadAndHandleClick(evt) {
      this.$emit('click')

      this.markAsRead()

      if (typeof this.handleClick === 'function') {
        this.handleClick(evt)
      }
    },
    async markAsRead() {
      const notification = this.notification
      if (notification.read) {
        return
      }

      try {
        await this.$store.dispatch('notification/markAsRead', { notification })
      } catch (err) {
        notifyIf(err, 'error')
      }
    },
  },
}
