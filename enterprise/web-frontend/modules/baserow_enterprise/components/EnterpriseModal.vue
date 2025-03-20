<template>
  <Modal ref="modal">
    <h2 class="box__title">
      {{ $t('enterpriseModal.title', { name }) }}
    </h2>
    <div>
      <p>
        {{ $t('enterpriseModal.description', { name }) }}
      </p>
      <div class="row margin-bottom-3">
        <div class="col col-6">
          <h3>{{ $t('enterpriseModal.premium') }}</h3>
          <PremiumFeatures></PremiumFeatures>
        </div>
        <div class="col col-6">
          <h3>{{ $t('enterpriseModal.enterprise') }}</h3>
          <EnterpriseFeatures></EnterpriseFeatures>
        </div>
      </div>
      <div>
        <Button
          type="primary"
          size="large"
          href="https://baserow.io/pricing"
          target="_blank"
          tag="a"
          >{{ $t('enterpriseModal.viewPricing') }}</Button
        >
        <component
          :is="buttonsComponent"
          v-if="workspace && buttonsComponent"
          :name="name"
          :workspace="workspace"
          @hide="hide()"
        ></component>
      </div>
    </div>
  </Modal>
</template>

<script>
import modal from '@baserow/modules/core/mixins/modal'
import PremiumFeatures from '@baserow_premium/components/PremiumFeatures'
import EnterpriseFeatures from '@baserow_enterprise/components/EnterpriseFeatures'

export default {
  name: 'EnterpriseModal',
  components: { PremiumFeatures, EnterpriseFeatures },
  mixins: [modal],
  props: {
    name: {
      type: String,
      required: true,
    },
    workspace: {
      type: [Object, null],
      required: false,
      default: null,
    },
  },
  computed: {
    buttonsComponent() {
      return this.$registry
        .get('plugin', 'premium')
        .getPremiumModalButtonsComponent()
    },
  },
}
</script>
