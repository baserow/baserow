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
          v-for="table in orderedTables"
          :key="table.id"
          class="tree__sub"
          :class="{ active: isTableActive(table) }"
        >
          <a class="tree__sub-link" @click="selectTable(application, table)">
            <i
              v-if="table.data_sync"
              class="context__menu-item-icon iconoir-data-transfer-down"
            ></i>
            {{ table.name }}
          </a>
        </li>
      </ul>
    </template>
  </li>
</template>

<script>
import { DatabaseApplicationType } from '@baserow/modules/database/applicationTypes'

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
    orderedTables() {
      return this.application.tables
        .map((table) => table)
        .sort((a, b) => a.order - b.order)
    },
  },
  methods: {
    selectTable(application, table) {
      this.$emit('selected-page', {
        application: DatabaseApplicationType.getType(),
        value: {
          database: application,
          table,
        },
      })
    },
    isTableActive(table) {
      return (
        this.page !== null &&
        this.page.application === DatabaseApplicationType.getType() &&
        this.page.value.table.id === table.id
      )
    },
  },
}
</script>
