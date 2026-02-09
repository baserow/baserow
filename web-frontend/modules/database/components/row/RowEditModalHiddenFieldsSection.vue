<template>
  <div>
    <div class="row-modal__hidden-separator">
      <div class="row-modal__hidden-separator-line"></div>
      <a
        class="row-modal__hidden-separator-link"
        @click="$emit('toggle-hidden-fields-visibility')"
      >
        {{
          $t(
            showHiddenFields
              ? 'rowEditModal.hideHiddenFields'
              : 'rowEditModal.showHiddenFields'
          )
        }}
        <i
          :class="[
            showHiddenFields
              ? 'iconoir-nav-arrow-up'
              : 'iconoir-nav-arrow-down',
          ]"
        ></i>
      </a>
      <div class="row-modal__hidden-separator-line"></div>
    </div>
    <div v-if="showHiddenFields">
      <slot></slot>
    </div>
  </div>
</template>

<script>
export default {
  name: 'RowModalHiddenFieldsSection',
  props: {
    showHiddenFields: {
      type: Boolean,
      required: true,
    },
  },
  emits: ['toggle-hidden-fields-visibility'],
}
</script>
