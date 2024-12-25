<template>
  <div class="badge-collaborator" :class="classes">
    <Avatar :initials="initials" size="small" rounded />

    <span class="badge-collaborator__label"><slot /></span>

    <i
      v-if="removeIcon"
      class="badge-collaborator__remove-icon iconoir-cancel"
      @click="$emit('remove')"
    ></i>
  </div>
</template>

<script>
import Avatar from '@baserow/modules/core/components/Avatar'
export default {
  name: 'BadgeCollaborator',
  components: {
    Avatar,
  },
  props: {
    /**
     * The initials to display if no image is provided
     */
    initials: {
      type: String,
      required: false,
      default: null,
    },
    /**
     * Display a remove icon on the badge if true
     */
    removeIcon: {
      type: Boolean,
      required: false,
      default: false,
    },
    /**
     * The size of the badge
     * Possible values are: `regular` | `small`
     */
    size: {
      type: String,
      required: false,
      default: 'regular',
      validator: function (value) {
        return ['regular', 'small'].includes(value)
      },
    },
  },
  computed: {
    classes() {
      const classObj = {
        [`badge-collaborator--${this.size}`]: this.size,
      }
      return classObj
    },
  },
}
</script>
