<template>
  <div class="grid-view__head-row-identifier">
    <i
      ref="contextAnchor"
      class="grid-view__head-row-identifier-dropdown iconoir-numbered-list-left"
      @click.prevent="toggle"
    ></i>

    <Context ref="context" overflow-scroll max-height-if-outside-viewport>
      <ul v-auto-overflow-scroll class="select__items">
        <li
          v-for="option in options"
          :key="option"
          class="select__item select__item--no-options"
          :class="{ active: option === rowIdentifierTypeSelected }"
        >
          <a class="select__item-link" @click="setRowIdentifierTypes(option)">
            <span class="select__item-name">
              <span class="select__item-text">{{
                $t(`gridViewIdentifierOptions.${option}`)
              }}</span>
            </span>
          </a>
          <i
            v-if="option === rowIdentifierTypeSelected"
            class="select__item-active-icon iconoir-check"
          ></i>
        </li>
      </ul>
    </Context>
  </div>
</template>

<script>
export default {
  name: 'GridViewRowIdentifierDropdown',
  props: {
    rowIdentifierTypeSelected: {
      type: String,
      required: true,
    },
  },
  emits: ['change'],
  computed: {
    options() {
      return ['id', 'count']
    },
  },
  methods: {
    toggle() {
      this.$refs.context.toggle(
        this.$refs.contextAnchor,
        'bottom',
        'left',
        10,
        4
      )
    },
    setRowIdentifierTypes(rowIdentifierType) {
      this.$refs.context.hide()
      this.$emit('change', rowIdentifierType)
    },
  },
}
</script>
