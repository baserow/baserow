<template>
  <a class="select__footer-create-link" v-on="$attrs">
    <i class="select__footer-create-icon iconoir-selection"></i>
    <span> {{ $t('addElementButton.label') }} </span>
    <i class="select__footer-create-link-icon iconoir-plus"></i>
  </a>
</template>

<script>
export default {
  name: 'AddElementButton',
}
</script>
