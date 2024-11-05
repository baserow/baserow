<template>
  <li
    class="tree__item"
    :class="{
      'tree__item--loading': application._.loading,
    }"
  >
    <div class="tree__action">
      <a class="tree__link" @click="$emit('selected', application)">
        <i class="tree__icon" :class="application._.type.iconClass"></i>
        <span class="tree__link-text">{{ application.name }}</span>
      </a>
    </div>
    <template v-if="application._.selected">
      <ul class="tree__subs">
        <li
          v-for="builderPage in orderedPages"
          :key="builderPage.id"
          class="tree__sub"
          :class="{ active: isPageActive(builderPage) }"
        >
          <a
            class="tree__sub-link"
            @click="selectPage(application, builderPage)"
          >
            {{ builderPage.name }}
          </a>
        </li>
      </ul>
    </template>
  </li>
</template>

<script>
import { BuilderApplicationType } from '@baserow/modules/builder/applicationTypes'

export default {
  name: 'TemplateSidebar',
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
  computed: {
    orderedPages() {
      return this.$store.getters['page/getVisiblePages'](this.application)
    },
  },
  methods: {
    selectPage(application, page) {
      this.$emit('selected-page', {
        application: BuilderApplicationType.getType(),
        value: {
          builder: application,
          page,
        },
      })
    },
    isPageActive(page) {
      return (
        this.page !== null &&
        this.page.application === BuilderApplicationType.getType() &&
        this.page.value.page.id === page.id
      )
    },
  },
}
</script>
