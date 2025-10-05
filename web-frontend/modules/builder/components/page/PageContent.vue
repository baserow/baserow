<template>
  <div class="page">
    <div class="page__sticky-header">
      <PageElement
        v-for="element in elementsPerPagePlaces[PAGE_PLACES.FIXED_HEADER]"
        :key="element.id"
        :element="element"
        :mode="mode"
        :application-context-additions="{
          recordIndexPath: [],
        }"
      />
    </div>
    <PageElement
      v-for="element in elementsPerPagePlaces[PAGE_PLACES.HEADER]"
      :key="element.id"
      :element="element"
      :mode="mode"
      :application-context-additions="{
        recordIndexPath: [],
      }"
    />
    <PageElement
      v-for="element in elementsPerPagePlaces[PAGE_PLACES.CONTENT]"
      :key="element.id"
      :element="element"
      :mode="mode"
      :application-context-additions="{
        recordIndexPath: [],
      }"
    />
    <PageElement
      v-for="element in elementsPerPagePlaces[PAGE_PLACES.FOOTER]"
      :key="element.id"
      :element="element"
      :mode="mode"
      :application-context-additions="{
        recordIndexPath: [],
      }"
    />
  </div>
</template>

<script>
import PageElement from '@baserow/modules/builder/components/page/PageElement'
import { dimensionMixin } from '@baserow/modules/core/mixins/dimensions'
import _ from 'lodash'
import { PAGE_PLACES } from '@baserow/modules/builder/enums'

export default {
  components: { PageElement },
  mixins: [dimensionMixin],
  inject: ['builder', 'mode'],
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
  computed: {
    elementsPerPagePlaces() {
      return _.groupBy([...this.elements, ...this.sharedElements], (element) =>
        this.$registry.get('element', element.type).getPagePlace(element)
      )
    },
    PAGE_PLACES() {
      return PAGE_PLACES
    },
    /* fixedHeaderElements() {
      return [...this.elements, ...this.sharedElements].filter(
        (element) =>
          this.$registry.get('element', element.type).getPagePlace(element) ===
          PAGE_PLACES.FIXED_HEADER
      )
    },
    contentElements() {
      return [...this.elements].filter(
        (element) =>
          this.$registry.get('element', element.type).getPagePlace(element) ===
          PAGE_PLACES.CONTENT
      )
    },
    headerElements() {
      return this.sharedElements.filter(
        (element) =>
          this.$registry.get('element', element.type).getPagePlace(element) ===
          PAGE_PLACES.HEADER
      )
    },
    footerElements() {
      return this.sharedElements.filter(
        (element) =>
          this.$registry.get('element', element.type).getPagePlace(element) ===
          PAGE_PLACES.FOOTER
      )
    }, */
  },
  watch: {
    'dimensions.width': {
      handler(newValue) {
        this.debounceGuessDevice(newValue)
      },
    },
  },
  mounted() {
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
