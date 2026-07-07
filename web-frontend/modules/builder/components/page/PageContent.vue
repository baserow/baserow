<template>
  <div class="page">
    <!-- Sections are built by pagePlaceElementsMixin. -->
    <component
      :is="section.tag"
      v-for="section in visiblePageElementSections"
      :key="section.key"
      :class="section.classNames"
    >
      <PageElement
        v-for="element in section.elements"
        :key="element.id"
        :element="element"
        :mode="mode"
        :application-context-additions="{
          page: currentPage,
          recordIndexPath: [],
        }"
      />
    </component>
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
