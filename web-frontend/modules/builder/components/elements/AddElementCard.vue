<template>
  <div
    :key="elementType.name"
    v-tooltip="disabled ? isDisallowedReason : elementType.description"
    class="add-element-card"
    :class="{ 'add-element-card--disabled': disabled }"
    @click.stop="onClick"
  >
    <div class="add-element-card__element-type">
      <div
        class="add-element-card__element-type-icon"
        :test="elementType.image"
        :style="{
          backgroundImage: `url(${elementType.image})`,
        }"
      ></div>
    </div>
    <div v-if="loading" class="loading"></div>
    <span v-else class="add-element-card__label">{{ elementType.name }}</span>
    <component
      :is="disallowedClickModal[0]"
      v-if="disallowedClickModal !== null"
      ref="deactivatedClickModal"
      v-bind="disallowedClickModal[1]"
      :name="elementType.name"
      :workspace="workspace"
    ></component>
  </div>
</template>

<script>
export default {
  name: 'AddElementCard',
  props: {
    elementType: {
      type: Object,
      required: true,
    },
    workspace: {
      type: Object,
      required: true,
    },
    builder: {
      type: Object,
      required: true,
    },
    page: {
      type: Object,
      required: true,
    },
    placeInContainer: {
      type: String,
      required: false,
      default: undefined,
    },
    parentElement: {
      type: Object,
      required: false,
      default: undefined,
    },
    beforeElement: {
      type: Object,
      required: false,
      default: undefined,
    },
    pagePlace: {
      type: String,
      required: false,
      default: undefined,
    },
    loading: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  computed: {
    disallowedClickModal() {
      return this.elementType.getDeactivatedClickModal({
        workspace: this.workspace,
      })
    },
    isDisallowedReason() {
      return this.elementType.isDisallowedReason({
        workspace: this.workspace,
        builder: this.builder,
        page: this.page,
        placeInContainer: this.placeInContainer,
        parentElement: this.parentElement,
        beforeElement: this.beforeElement,
        pagePlace: this.pagePlace,
      })
    },
    disabled() {
      return !!this.isDisallowedReason
    },
  },
  methods: {
    onClick(event) {
      if (this.disallowedClickModal !== null) {
        this.$refs.deactivatedClickModal.show()
      } else if (!this.disabled) {
        this.$emit('click', event)
      }
    },
  },
}
</script>
