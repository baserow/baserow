<template>
  <header class="layout__col-2-1 header header--space-between">
    <ul class="header__filter">
      <li class="header__filter-item">
        <a data-item-type="settings" class="header__filter-link"
          ><i class="header__filter-icon iconoir-settings"></i>
          <span class="header__filter-name">{{
            $t('automationHeader.settingsBtn')
          }}</span>
        </a>
      </li>

      <li class="header__filter-item">
        <a data-item-type="settings" class="header__filter-link"
          ><i class="header__filter-icon baserow-icon-history"></i>
          <span class="header__filter-name">{{
            $t('automationHeader.historyBtn')
          }}</span>
        </a>
      </li>
    </ul>

    <div class="header__right">
      <span class="header__switch-container">
        <Badge color="cyan" rounded size="small">{{
          $t('automationHeader.switchLabel')
        }}</Badge>
        <SwitchInput
          small
          :value="switchValue"
          @input="switchValue = !switchValue"
        ></SwitchInput>
      </span>

      <div class="header__buttons header__buttons--with-separator">
        <Button icon="iconoir-play" type="secondary" disabled>{{
          $t('automationHeader.runOnceBtn')
        }}</Button>
        <Button disabled>{{ $t('automationHeader.publishBtn') }}</Button>
      </div>
    </div>
  </header>
</template>

<script>
import { defineComponent, ref } from 'vue'

export default defineComponent({
  name: 'AutomationHeader',
  components: {},
  props: {
    automation: {
      type: Object,
      required: true,
    },
  },
  setup() {
    const switchValue = ref(false)

    return {
      switchValue,
    }
  },
})
</script>
