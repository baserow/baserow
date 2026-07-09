<template>
  <div class="skeleton">
    <div class="skeleton skeleton--row skeleton--no-padding">
      <div
        class="skeleton__item skeleton__item--heading skeleton__item--w-md"
      ></div>
    </div>
    <div class="skeleton skeleton--row skeleton--no-padding">
      <div class="skeleton__item skeleton__item--block skeleton__item--w-half"></div>
      <div class="skeleton__item skeleton__item--block skeleton__item--w-half"></div>
    </div>
    <div class="skeleton__item skeleton__item--w-half"></div>
    <div class="skeleton__item skeleton__item--w-half"></div>
    <div class="skeleton__item skeleton__item--w-half"></div>
    <div class="skeleton__item skeleton__item--w-half"></div>
  </div>
</template>

<script>
export default {
  name: 'WorkspacePageSkeleton',
}
</script>
