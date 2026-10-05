<template>
  <Expandable class="setup-guide">
    <template #header="{ toggle, expanded }">
      <a class="setup-guide__link" @click.prevent="toggle">
        <i class="iconoir-info-empty"></i>
        <span>{{ title }}</span>
        <i
          class="setup-guide__chevron iconoir-nav-arrow-down"
          :class="{ 'setup-guide__chevron--expanded': expanded }"
        ></i>
      </a>
    </template>
    <div class="setup-guide__body">
      <p v-if="intro" class="setup-guide__intro">{{ intro }}</p>
      <ol class="setup-guide__steps">
        <slot></slot>
      </ol>
    </div>
  </Expandable>
</template>

<script>
/**
 * A collapsible "how to set this up" guide shown inside a form: a muted
 * heading row with an info icon and chevron, an optional intro line and a
 * numbered list of steps passed as `<li>` elements in the default slot.
 */
export default {
  name: 'SetupGuide',
  props: {
    title: {
      type: String,
      required: true,
    },
    intro: {
      type: String,
      required: false,
      default: '',
    },
  },
}
</script>
