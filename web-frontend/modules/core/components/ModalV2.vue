<template>
  <div
    v-if="open"
    ref="modalOverlay"
    class="modalv2__overlay"
    @click="outside($event)"
  >
    <div
      ref="modalv2"
      class="modalv2"
      :class="{
        'modalv2--full-height': fullHeight && size !== 'fullscreen',
        'modalv2--with-sidebar': sidebar,
        'modalv2--with-topbar': topbar,
        'modalv2--with-header': header,
        'modalv2--with-right-sidebar': rightSidebar,
        'modalv2--with-left-sidebar': leftSidebar,
        'modalv2--fullscreen': size === 'fullscreen' && !fullHeight,
        'modalv2--large': size === 'large',
        'modalv2--small': size === 'small',
        'modalv2--tiny': size === 'tiny',
      }"
    >
      <div v-if="topbar" class="modalv2__topbar">
        <div class="modalv2__topbar-content">
          <slot name="topbar-content"></slot>
        </div>

        <div class="modalv2__topbar-actions">
          <ul class="modalv2__topbar-icons">
            <slot name="topbar-actions"></slot>
          </ul>

          <div v-if="closeButton" class="modalv2__topbar-icon-close">
            <i class="iconoir-cancel" @click="hide()"></i>
          </div>
        </div>
      </div>

      <div class="modalv2__wrapper">
        <div v-if="leftSidebar" class="modalv2__sidebar modalv2__sidebar--left">
          <slot name="sidebar-content"></slot>
        </div>

        <div ref="contentWrapper" class="modalv2__content-wrapper">
          <div v-if="header" ref="header" class="modalv2__header">
            <slot name="header-content"></slot>
          </div>

          <div ref="content" class="modalv2__content">
            <slot name="content"></slot>
          </div>

          <div v-if="footer" ref="footer" class="modalv2__footer">
            <slot name="footer-content"></slot>
          </div>
        </div>

        <a v-if="closeButton && !topbar" class="modalv2__close" @click="hide()">
          <i class="iconoir-cancel"></i>
        </a>

        <div
          v-if="rightSidebar && !rightSidebarCollapsed"
          class="modalv2__sidebar modalv2__sidebar--right"
        >
          <slot name="sidebar-content"></slot>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import baseModalV2 from '@baserow/modules/core/mixins/baseModalV2'

export default {
  name: 'ModalV2',
  mixins: [baseModalV2],

  props: {
    /**
     * If the modal has a topbar.
     */
    topbar: {
      type: Boolean,
      default: false,
      required: false,
    },
    /**
     * If the modal has a left sidebar.
     */
    leftSidebar: {
      type: Boolean,
      default: false,
      required: false,
    },
    /**
     * If the modal has a right sidebar.
     */
    rightSidebar: {
      type: Boolean,
      default: false,
      required: false,
    },
    /**
     * If the modal has a header.
     */
    header: {
      type: Boolean,
      default: true,
      required: false,
    },
    /**
     * If the modal has a footer.
     */
    footer: {
      type: Boolean,
      default: true,
      required: false,
    },
    /**
     * The size of the button.
     */
    size: {
      required: false,
      type: String,
      default: 'regular',
      validator(value) {
        return ['tiny', 'small', 'regular', 'large', 'fullscreen'].includes(
          value
        )
      },
    },
    /**
     * If the modal can be closed with a click outside of the modal.
     */
    canClose: {
      type: Boolean,
      default: true,
      required: false,
    },
    /**
     * If the modal has a close button.
     */
    closeButton: {
      type: Boolean,
      default: true,
      required: false,
    },
    /**
     * If the modal is full height.
     */
    fullHeight: {
      type: Boolean,
      default: false,
      required: false,
    },
  },
  data() {
    return {
      rightSidebarCollapsed: false,
    }
  },
  computed: {
    sidebar() {
      return this.leftSidebar || this.rightSidebar
    },
  },
  methods: {
    collapseRightSidebar() {
      this.rightSidebarCollapsed = !this.rightSidebarCollapsed
    },
  },
}
</script>
