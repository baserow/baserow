<template>
  <div
    class="sortings__order"
    :class="{ 'sortings__order--disabled': disabled }"
  >
    <template v-if="Object.keys(sortTypes).length === 1">
      <a
        class="sortings__order-item"
        :class="{ active: order === 'ASC' }"
        @click="$emit('update-order', { order: 'ASC', type })"
      >
        <template v-if="sortIndicator[0] === 'text'"
          >{{ sortIndicator[1] }}
        </template>
        <i v-if="sortIndicator[0] === 'icon'" :class="sortIndicator[1]"></i>

        <i class="iconoir-arrow-right"></i>

        <template v-if="sortIndicator[0] === 'text'"
          >{{ sortIndicator[2] }}
        </template>
        <i v-if="sortIndicator[0] === 'icon'" :class="sortIndicator[2]"></i>
      </a>
      <a
        class="sortings__order-item"
        :class="{ active: order === 'DESC' }"
        @click="$emit('update-order', { order: 'DESC', type })"
      >
        <template v-if="sortIndicator[0] === 'text'"
          >{{ sortIndicator[2] }}
        </template>
        <i v-if="sortIndicator[0] === 'icon'" :class="sortIndicator[2]"></i>

        <i class="iconoir-arrow-right"></i>

        <template v-if="sortIndicator[0] === 'text'"
          >{{ sortIndicator[1] }}
        </template>
        <i v-if="sortIndicator[0] === 'icon'" :class="sortIndicator[1]"></i>
      </a>
    </template>
    <template v-else>
      <Dropdown
        :value="`${type}-${order}`"
        :fixed-items="true"
        class="sortings__order-dropdown"
        @input="dropdownItemChange"
      >
        <DropdownItem
          v-for="item in dropdownItems"
          :key="item.value"
          :name="item.name"
          :value="item.value"
        ></DropdownItem>
      </Dropdown>
    </template>
  </div>
</template>

<script>
export default {
  name: 'ViewSortOrder',
  props: {
    disabled: {
      type: Boolean,
      required: false,
      default: false,
    },
    sortTypes: {
      type: Object,
      required: true,
    },
    type: {
      type: String,
      required: true,
    },
    order: {
      type: String,
      required: true,
    },
  },
  computed: {
    sortIndicator() {
      return this.sortTypes[this.type].indicator
    },
    dropdownItems() {
      const items = []
      Object.entries(this.sortTypes).forEach(([type, sortObject]) => {
        const indicator = sortObject.indicator
        items.push({
          name: `${indicator[1]} -> ${indicator[2]}`,
          value: `${type}-ASC`,
        })
        items.push({
          name: `${indicator[2]} -> ${indicator[1]}`,
          value: `${type}-DESC`,
        })
      })
      return items
    },
  },
  methods: {
    dropdownItemChange(value) {
      const [type, order] = value.split('-')
      this.$emit('update-order', { order, type })
    },
  },
}
</script>
