<template>
  <li
    class="tree__item"
    :class="{
      'tree__item--loading': application._.loading,
    }"
  >
    <div
      class="tree__action"
      :class="{ 'tree__action--highlighted': application._.selected }"
    >
      <a class="tree__link" @click="selectWhiteboard(application)">
        <i class="tree__icon" :class="application._.type.iconClass"></i>
        <span class="tree__link-text">{{ application.name }}</span>
      </a>
    </div>
  </li>
</template>

<script>
import { WhiteboardApplicationType } from '@baserow/modules/whiteboard/applicationTypes'

export default {
  name: 'WhiteboardTemplateSidebar',
  props: {
    application: {
      type: Object,
      required: true,
    },
    page: {
      required: true,
      validator: (prop) => typeof prop === 'object' || prop === null,
    },
  },
  emits: ['selected', 'selected-page'],
  methods: {
    selectWhiteboard(application) {
      this.$emit('selected', application)
      this.$emit('selected-page', {
        application: WhiteboardApplicationType.getType(),
        value: {
          whiteboard: application,
        },
      })
    },
  },
}
</script>
