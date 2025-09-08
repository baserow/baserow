<template>
  <div
    v-if="open || keepContent"
    v-show="(keepContent && open) || !keepContent"
    ref="modalWrapper"
    class="modal__wrapper"
    @click="outside($event)"
  >
    <div
      class="modal__box"
      :class="{
        'modal__box--full-height': fullHeight,
        'modal__box--full-max-height': !fullHeight && contentScrollable,
        'modal__box--with-sidebar': sidebar,
        'modal__box--full-screen': fullScreen,
        'modal__box--wide': wide,
        'modal__box--small': small,
        'modal__box--tiny': tiny,
        'modal__box--right': right,
        'modal__box--no-padding': !boxPadding,
      }"
    >
      <template v-if="sidebar">
        <div
          v-if="leftSidebar"
          class="modal__box-sidebar modal__box-sidebar--left"
          :class="{ 'modal__box-sidebar--scrollable': leftSidebarScrollable }"
        >
          <slot name="sidebar"></slot>
        </div>
        <div
          class="modal__box-content"
          :class="{
            'modal__box-content--scrollable': contentScrollable,
            'modal__box-content-no-padding': !contentPadding,
          }"
        >
          <slot name="content"></slot>
          <div class="modal__actions">
            <a
              v-if="closeButton && canClose"
              role="button"
              :title="$t('action.close')"
              class="modal__close"
              @click="hide()"
            >
              <i class="iconoir-cancel"></i>
            </a>

            <a
              v-if="collapsibleRightSidebar"
              class="modal__collapse"
              @click="collapseSidebar"
            >
              <i
                :class="{
                  'iconoir-fast-arrow-right': !sidebarCollapsed,
                  'iconoir-fast-arrow-left': sidebarCollapsed,
                }"
              ></i>
            </a>
            <slot name="actions"></slot>
          </div>
        </div>

        <div
          v-if="rightSidebar"
          class="modal__box-sidebar modal__box-sidebar--right"
          :class="{
            'modal__box-sidebar--scrollable': rightSidebarScrollable,
            'modal__box-sidebar--collapsed': sidebarCollapsed,
          }"
        >
          <slot v-if="!sidebarCollapsed" name="sidebar"></slot>
        </div>
      </template>
      <template v-if="!sidebar">
        <slot></slot>
        <slot name="content"></slot>
        <div class="modal__actions">
          <a
            v-if="closeButton && canClose"
            class="modal__close"
            @click="hide()"
          >
            <i class="iconoir-cancel"></i>
          </a>
          <slot name="actions"></slot>
        </div>
      </template>
    </div>
  </div>
</template>

<script>
import baseModal from '@baserow/modules/core/mixins/baseModal'

export default {
  name: 'Modal',
  mixins: [baseModal],
  props: {
    leftSidebar: {
      type: Boolean,
      default: false,
      required: false,
    },
    rightSidebar: {
      type: Boolean,
      default: false,
      required: false,
    },
    fullScreen: {
      type: Boolean,
      default: false,
      required: false,
    },
    wide: {
      type: Boolean,
      default: false,
      required: false,
    },
    small: {
      type: Boolean,
      default: false,
      required: false,
    },
    tiny: {
      type: Boolean,
      default: false,
      required: false,
    },
    closeButton: {
      type: Boolean,
      default: true,
      required: false,
    },
    fullHeight: {
      type: Boolean,
      default: false,
      required: false,
    },
    leftSidebarScrollable: {
      type: Boolean,
      default: false,
      required: false,
    },
    contentScrollable: {
      type: Boolean,
      default: false,
      required: false,
    },
    contentPadding: {
      type: Boolean,
      default: true,
      required: false,
    },
    rightSidebarScrollable: {
      type: Boolean,
      default: false,
      required: false,
    },
    collapsibleRightSidebar: {
      type: Boolean,
      default: false,
      required: false,
    },
    boxPadding: {
      type: Boolean,
      default: true,
      required: false,
    },
    right: {
      type: Boolean,
      default: false,
      required: false,
    },
    // This flag allow to keep the modal content in case you want it to be available.
    // Useful if you have a form inside the modal that is a sub part of the current
    // form.
    keepContent: {
      type: Boolean,
      default: false,
      required: false,
    },
  },
  data() {
    return {
      sidebarCollapsed: false,
    }
  },
  computed: {
    sidebar() {
      return this.leftSidebar || this.rightSidebar
    },
  },
  methods: {
    collapseSidebar() {
      this.sidebarCollapsed = !this.sidebarCollapsed
    },
  },
}
</script>
