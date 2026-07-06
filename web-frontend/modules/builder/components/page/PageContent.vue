<template>
  <div class="page">
    <div
      v-if="fixedHeaderElements.length !== 0"
      class="page__fixed-stack page__fixed-stack--top"
    >
      <PageElement
        v-for="element in fixedHeaderElements"
        :key="element.id"
        :element="element"
        :mode="mode"
        :application-context-additions="{
          page: currentPage,
          recordIndexPath: [],
        }"
      />
    </div>
    <header v-if="normalHeaderElements.length !== 0" class="page__header">
      <PageElement
        v-for="element in normalHeaderElements"
        :key="element.id"
        :element="element"
        :mode="mode"
        :application-context-additions="{
          page: currentPage,
          recordIndexPath: [],
        }"
      />
    </header>
    <div class="page__content">
      <PageElement
        v-for="element in elements"
        :key="element.id"
        :element="element"
        :mode="mode"
        :application-context-additions="{
          page: currentPage,
          recordIndexPath: [],
        }"
      />
    </div>
    <footer v-if="normalFooterElements.length !== 0" class="page__footer">
      <PageElement
        v-for="element in normalFooterElements"
        :key="element.id"
        :element="element"
        :mode="mode"
        :application-context-additions="{
          page: currentPage,
          recordIndexPath: [],
        }"
      />
    </footer>
    <div
      v-if="fixedFooterElements.length !== 0"
      class="page__fixed-stack page__fixed-stack--bottom"
    >
      <PageElement
        v-for="element in fixedFooterElements"
        :key="element.id"
        :element="element"
        :mode="mode"
        :application-context-additions="{
          page: currentPage,
          recordIndexPath: [],
        }"
      />
    </div>
  </div>
</template>

<script>
import PageElement from '@baserow/modules/builder/components/page/PageElement'
import { dimensionMixin } from '@baserow/modules/core/mixins/dimensions'
import _ from 'lodash'
import pagePlaceElementsMixin from '@baserow/modules/builder/mixins/pagePlaceElements'

export default {
  components: { PageElement },
  mixins: [dimensionMixin, pagePlaceElementsMixin],
  inject: ['builder', 'mode', 'currentPage'],
  props: {
    path: {
      type: String,
      required: true,
    },
    params: {
      type: Object,
      required: true,
    },
    elements: {
      type: Array,
      required: true,
    },
    sharedElements: {
      type: Array,
      required: true,
    },
  },
  watch: {
    'dimensions.width': {
      handler(newValue) {
        this.debounceGuessDevice(newValue)
      },
    },
  },
  mounted() {
    const device = this.closestDeviceType(window.innerWidth)
    this.$store.dispatch('page/setDeviceTypeSelected', device.getType())
    this.dimensions.targetElement = document.documentElement
  },
  methods: {
    /**
     * Returns the device type that is the closest to the given observer width.
     * It does this by sorting the device types by order ASC (as we want to start
     * with the smallest screen) and then checking if the observer width is smaller
     * (or in the case of desktop, unlimited with `null`) than the max width of
     * the device. If it is, the device is returned.
     *
     * @param {number} observerWidth The width of the observer.
     * @returns {DeviceType|null}
     */
    closestDeviceType(observerWidth) {
      const deviceTypes = Object.values(this.$registry.getAll('device'))
        .sort((deviceA, deviceB) => deviceA.getOrder() - deviceB.getOrder())
        .reverse()
      for (const device of deviceTypes) {
        if (device.maxWidth === null || observerWidth <= device.maxWidth) {
          return device
        }
      }
      return null
    },
    debounceGuessDevice: _.debounce(function (newWidth) {
      const device = this.closestDeviceType(newWidth)
      this.$store.dispatch('page/setDeviceTypeSelected', device.getType())
    }, 300),
  },
}
</script>
