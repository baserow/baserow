<template>
  <ItemPickerCard
    v-tooltip="disabled ? isDisallowedReason : elementType.description"
    :name="elementType.name"
    :image="elementType.image"
    :unavailable="disabled"
    :loading="loading"
    @click.stop="onClick"
  >
    <component
      :is="disallowedClickModal[0]"
      v-if="disallowedClickModal !== null"
      ref="deactivatedClickModal"
      v-bind="disallowedClickModal[1]"
      :name="elementType.name"
      :workspace="workspace"
    ></component>
  </ItemPickerCard>
</template>

<script>
import ItemPickerCard from '@baserow/modules/core/components/ItemPickerCard'

export default {
  name: 'AddElementCard',
  components: { ItemPickerCard },
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
    afterElement: {
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
  emits: ['click'],
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
        afterElement: this.afterElement,
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
