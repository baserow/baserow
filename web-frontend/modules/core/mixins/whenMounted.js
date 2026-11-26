import { createWhenMounted } from '@baserow/modules/core/utils/whenMounted'

export default {
  data() {
    return { mountQueue: createWhenMounted() }
  },
  mounted() {
    this.mountQueue.mounted()
  },
  methods: {
    whenMounted(callback, ...args) {
      this.mountQueue.whenMounted(callback, ...args)
    },
  },
}
