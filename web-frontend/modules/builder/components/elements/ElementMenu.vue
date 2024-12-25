<template>
  <div class="element-preview__menu" @click.stop>
    <span v-if="isDuplicating" class="element-preview__menu-item disabled">
      <div class="loading"></div>
    </span>
    <a v-else class="element-preview__menu-item" @click="$emit('duplicate')">
      <i class="iconoir-copy"></i>
      <span class="element-preview__menu-item-description">
        {{ $t('action.duplicate') }} (d)
      </span>
    </a>
    <a
      v-if="hasParent"
      class="element-preview__menu-item"
      @click="$emit('select-parent')"
    >
      <i class="iconoir-scale-frame-enlarge"></i>
      <span class="element-preview__menu-item-description">
        {{ $t('elementMenu.selectParent') }} (p)
      </span>
    </a>
    <a
      v-if="isDirectionVisible(DIRECTIONS.LEFT)"
      class="element-preview__menu-item"
      :class="{
        'element-preview__menu-item--disabled': !isAllowedDirection(
          DIRECTIONS.LEFT
        ),
      }"
      @click="$emit('move', DIRECTIONS.LEFT)"
    >
      <i class="iconoir-nav-arrow-left"></i>
      <span class="element-preview__menu-item-description">
        {{ $t('elementMenu.moveLeft') }}
      </span>
    </a>
    <a
      v-if="isDirectionVisible(DIRECTIONS.RIGHT)"
      class="element-preview__menu-item"
      :class="{
        'element-preview__menu-item--disabled': !isAllowedDirection(
          DIRECTIONS.RIGHT
        ),
      }"
      @click="$emit('move', DIRECTIONS.RIGHT)"
    >
      <i class="iconoir-nav-arrow-right"></i>
      <span class="element-preview__menu-item-description">
        {{ $t('elementMenu.moveRight') }}
      </span>
    </a>
    <a
      v-if="isDirectionVisible(DIRECTIONS.BEFORE)"
      class="element-preview__menu-item"
      :class="{
        'element-preview__menu-item--disabled': !isAllowedDirection(
          DIRECTIONS.BEFORE
        ),
      }"
      @click="$emit('move', DIRECTIONS.BEFORE)"
    >
      <i class="iconoir-nav-arrow-up"></i>
      <span class="element-preview__menu-item-description">
        {{ $t('elementMenu.moveUp') }}
      </span>
    </a>
    <a
      v-if="isDirectionVisible(DIRECTIONS.AFTER)"
      class="element-preview__menu-item"
      :class="{
        'element-preview__menu-item--disabled': !isAllowedDirection(
          DIRECTIONS.AFTER
        ),
      }"
      @click="$emit('move', DIRECTIONS.AFTER)"
    >
      <i class="iconoir-nav-arrow-down"></i>
      <span class="element-preview__menu-item-description">
        {{ $t('elementMenu.moveDown') }}
      </span>
    </a>
    <a class="element-preview__menu-item" @click="$emit('delete')">
      <i class="iconoir-bin"></i>
      <span class="element-preview__menu-item-description">
        {{ $t('action.delete') }} (del)
      </span>
    </a>
  </div>
</template>

<script>
import { DIRECTIONS } from '@baserow/modules/builder/enums'

export default {
  name: 'ElementMenu',
  props: {
    isDuplicating: {
      type: Boolean,
      required: false,
      default: false,
    },
    hasParent: {
      type: Boolean,
      required: false,
      default: false,
    },
    directions: {
      type: Array,
      required: false,
      default: () => [DIRECTIONS.BEFORE, DIRECTIONS.AFTER],
    },
    allowedDirections: {
      type: Array,
      required: false,
      default: () => [],
    },
  },
  computed: {
    DIRECTIONS: () => DIRECTIONS,
  },
  methods: {
    isDirectionVisible(direction) {
      return this.directions.includes(direction)
    },
    isAllowedDirection(direction) {
      return this.allowedDirections.includes(direction)
    },
  },
}
</script>
