<template>
  <div class="made-with-baserow-wrapper">
    <slot></slot>
    <div class="made-with-baserow">
      <img
        src="@baserow_enterprise/assets/images/builder/made_with_baserow.svg"
        alt="Made with Baserow"
      />
    </div>
  </div>
</template>

<style lang="scss" scoped>
.made-with-baserow-wrapper {
  position: relative;
  min-height: 100vh;
}

.made-with-baserow {
  position: fixed;
  bottom: 12px;
  right: 12px;
  z-index: 100;
  pointer-events: none;
}
</style>
