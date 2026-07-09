<template>
  <div>
    <header class="layout__col-2-1 header">
      <div class="header__loading"></div>
    </header>
    <div class="layout__col-2-2">
      <div class="skeleton">
        <div
          class="skeleton__item skeleton__item--heading skeleton__item--w-md"
        ></div>
        <div class="skeleton skeleton--row skeleton--no-padding">
          <div
            class="skeleton__item skeleton__item--block skeleton__item--w-half"
          ></div>
          <div
            class="skeleton__item skeleton__item--block skeleton__item--w-half"
          ></div>
        </div>
        <div class="skeleton__item skeleton__item--block"></div>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'DashboardSkeleton',
}
</script>
