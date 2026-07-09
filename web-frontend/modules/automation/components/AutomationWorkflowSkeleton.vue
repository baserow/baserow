<template>
  <div>
    <header class="layout__col-2-1 header">
      <div class="header__loading"></div>
    </header>
    <div class="layout__col-2-2">
      <div class="skeleton" style="align-items: center">
        <div
          class="skeleton__item skeleton__item--block skeleton__item--w-md"
        ></div>
        <div
          class="skeleton__item skeleton__item--block skeleton__item--w-md"
        ></div>
        <div
          class="skeleton__item skeleton__item--block skeleton__item--w-md"
        ></div>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'AutomationWorkflowSkeleton',
}
</script>
