<template>
  <div
    :id="$slots.content ? undefined : forInput"
    class="dropdown"
    :class="{
      'dropdown--floating': !showInput,
      'dropdown--disabled': disabled,
      'dropdown--large': size === 'large',
      'dropdown--error': error,
      'dropdown--loading': loading,
      'dropdown--custom-content': !!$slots.content,
      'dropdown--with-suffix': !!$slots.suffix,
    }"
    :tabindex="$slots.content ? undefined : realTabindex"
    :role="$slots.content ? undefined : 'list'"
    @focusin="!$slots.content && show()"
    @focusout="!$slots.content && focusout($event)"
  >
    <button
      v-if="$slots.content && showInput"
      :id="forInput"
      ref="trigger"
      v-tooltip.focus="tooltip"
      class="dropdown__selected"
      type="button"
      :tabindex="tabindex"
      :disabled="disabled || loading"
      :aria-expanded="open"
      :aria-description="tooltip || undefined"
      @click="toggle()"
      @keydown.esc.stop.prevent="close"
    >
      <slot name="display">
        <span class="dropdown__selected-placeholder">{{
          placeholder || $t('action.makeChoice')
        }}</span>
      </slot>
      <span v-if="loading" class="dropdown__toggle-loading" />
      <i
        v-else-if="!$slots.suffix"
        class="dropdown__toggle-icon iconoir-nav-arrow-down"
      />
    </button>
    <a v-else-if="showInput" class="dropdown__selected" @click="show()">
      <template v-if="hasValue()">
        <slot name="selectedValue">
          <template v-if="multiple">
            <span
              class="dropdown__selected-text"
              :title="selectedName.join(', ')"
              >{{ selectedName.join(', ') }}</span
            >
          </template>
          <template v-else>
            <i
              v-if="selectedIcon"
              class="dropdown__selected-icon"
              :class="selectedIcon"
            />
            <img
              v-if="selectedImage"
              class="dropdown__selected-image"
              :src="selectedImage"
            />
            <span class="dropdown__selected-text" :title="selectedName">{{
              selectedName
            }}</span>
          </template>
        </slot>
      </template>
      <template v-else>
        <slot name="defaultValue">
          <span class="dropdown__selected-placeholder">{{
            placeholder ? placeholder : $t('action.makeChoice')
          }}</span>
        </slot>
      </template>

      <span v-if="loading" class="dropdown__toggle-loading"></span>
      <i v-else class="dropdown__toggle-icon iconoir-nav-arrow-down"></i>
    </a>
    <template v-if="$slots.content">
      <div v-if="$slots.suffix" class="dropdown__suffix">
        <slot name="suffix" />
      </div>
      <!-- Custom content owns its selection and keyboard behavior. -->
      <Context
        ref="context"
        tabindex="-1"
        @shown="onContentShown"
        @hidden="onContentHidden"
        @keydown.esc.stop.prevent="close"
      >
        <slot name="content" :close="close" />
      </Context>
    </template>
    <div
      v-else
      ref="itemsContainer"
      class="dropdown__items"
      :class="{
        hidden: !open && !openOnMount,
        'dropdown__items--fixed': fixedItemsImmutable,
        'dropdown__items--max-width': maxWidth,
      }"
    >
      <div v-if="showSearch" class="select__search">
        <i class="select__search-icon iconoir-search"></i>
        <input
          ref="search"
          v-model="query"
          type="text"
          class="select__search-input"
          :placeholder="searchText === null ? $t('action.search') : searchText"
          tabindex="0"
          @keyup="search(query)"
        />
      </div>
      <ul
        v-show="hasItems && hasDropdownItem"
        ref="items"
        v-auto-overflow-scroll
        class="select__items"
        :class="{ 'select__items--no-max-height': fixedItemsImmutable }"
        tabindex="-1"
      >
        <slot></slot>
      </ul>
      <div v-if="!hasItems || !hasDropdownItem" class="select__items--empty">
        <slot name="emptyState">
          {{ $t('dropdown.empty') }}
        </slot>
      </div>
      <div v-if="showFooter" class="select__footer">
        <slot name="footer"></slot>
      </div>
    </div>
  </div>
</template>

<script>
import dropdown from '@baserow/modules/core/mixins/dropdown'
import Context from '@baserow/modules/core/components/Context'

export default {
  name: 'Dropdown',
  components: { Context },
  mixins: [dropdown],
  props: {
    /**
     * Replaces the toggle icon with a spinner and prevents the value from being
     * changed until loading has finished.
     */
    loading: {
      type: Boolean,
      required: false,
      default: false,
    },
    /** Explanation shown on hover and keyboard focus of the trigger. */
    tooltip: {
      type: String,
      default: null,
    },
  },
  emits: ['show', 'hide'],
  watch: {
    loading(value) {
      if (value) {
        this.hide()
      }
    },
  },
  methods: {
    async show(target) {
      if (this.loading) {
        return
      }
      if (!this.$slots.content) {
        return dropdown.methods.show.call(this, target)
      }
      if (this.disabled || this.open || this.opening) return
      this.opening = true
      try {
        if (this.beforeShow && (await this.beforeShow()) === false) return
        if (this.disabled || this.loading || !this.$refs.context) return
        const trigger = target || this.$refs.trigger
        if (!trigger) return
        this.opener = trigger
        await this.$refs.context.show(trigger, 'bottom', 'left', 4)
      } finally {
        this.opening = false
      }
    },
    hide() {
      if (!this.$slots.content) return dropdown.methods.hide.call(this)
      if (this.open) this.$refs.context.hide()
    },
    close() {
      const trigger = this.opener || this.$refs.trigger
      this.hide()
      trigger?.focus?.()
    },
    onContentShown() {
      this.open = true
      this.$refs.context.getTeleportedElement()?.focus()
      this.$emit('show')
    },
    onContentHidden() {
      this.open = false
      this.opener = null
      this.$emit('hide')
    },
  },
}
</script>
