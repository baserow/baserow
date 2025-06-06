<template>
  <Modal :left-sidebar="true">
    <template #sidebar>
      <template v-for="(features, planName) in paidFeaturePlans">
        <div :key="planName + 'title'" class="modal-sidebar__title">
          {{ planName }}
        </div>
        <ul :key="planName + 'items'" class="modal-sidebar__nav">
          <li v-for="feature in features" :key="feature.getType()">
            <a
              class="modal-sidebar__nav-link"
              :class="{ active: selectedType === feature.getType() }"
              @click="selectedType = feature.getType()"
            >
              <i
                class="modal-sidebar__nav-icon"
                :class="feature.getIconClass()"
              ></i>
              {{ feature.getName() }}
            </a>
          </li>
        </ul>
      </template>
    </template>
    <template v-if="selectedType !== null" #content>
      <h2 class="box__title">
        {{ name }}
      </h2>
      <div v-if="image" class="paid-features__image margin-bottom-3">
        <div class="paid-features__image-header">
          <div
            class="paid-features__image-circle paid-features__image-circle--red"
          ></div>
          <div
            class="paid-features__image-circle paid-features__image-circle--orange"
          ></div>
          <div
            class="paid-features__image-circle paid-features__image-circle--green"
          ></div>
        </div>
        <img :src="image" :alt="name" class="paid-features__image-img" />
      </div>
      <MarkdownIt :content="content" class="margin-bottom-3" />
      <p>
        {{ $t('paidFeaturesModal.description', { plan }) }}
      </p>
      <div>
        <Button
          type="primary"
          size="large"
          :href="getPricingURL"
          target="_blank"
          tag="a"
          >{{ $t('paidFeaturesModal.viewPricing') }}</Button
        >
        <component
          :is="buttonsComponent"
          v-if="workspace && buttonsComponent"
          :name="name"
          :workspace="workspace"
          @hide="hide()"
        ></component>
      </div>
    </template>
  </Modal>
</template>

<script>
import modal from '@baserow/modules/core/mixins/modal'
import MarkdownIt from '@baserow/modules/core/components/MarkdownIt'
import SettingsService from '@baserow/modules/core/services/settings'
import { getPricingURL } from '@baserow_premium/utils/pricing'

export default {
  name: 'PaidFeaturesModal',
  components: { MarkdownIt },
  mixins: [modal],
  props: {
    workspace: {
      type: [Object, null],
      required: false,
      default: null,
    },
    initialSelectedType: {
      type: String,
      required: false,
      default: null,
    },
  },
  data() {
    return {
      selectedType: null,
      instanceId: null,
    }
  },
  computed: {
    getPricingURL() {
      return this.$config.BASEROW_PRICING_URL || getPricingURL(this.instanceId)
    },
    paidFeaturePlans() {
      const plans = {}
      Object.values(this.$registry.getAll('paidFeature')).forEach((feature) => {
        const plan = feature.getPlan()
        if (!Object.prototype.hasOwnProperty.call(plans, plan)) {
          plans[plan] = []
        }
        plans[plan].push(feature)
      })
      return plans
    },
    selectedPaidFeature() {
      return this.$registry.get('paidFeature', this.selectedType)
    },
    plan() {
      return this.selectedPaidFeature.getPlan()
    },
    name() {
      return this.selectedPaidFeature.getName()
    },
    image() {
      return this.selectedPaidFeature.getImage()
    },
    content() {
      return this.selectedPaidFeature.getContent()
    },
    buttonsComponent() {
      return this.$registry
        .get('plugin', 'premium')
        .getPremiumModalButtonsComponent()
    },
  },
  methods: {
    async loadInstanceID() {
      if (this.instanceId === null && this.$store.getters['auth/isStaff']) {
        try {
          // It is okay to not show a loading animation here because the request is
          // very fast, and if no instance ID is provided, then the user is still
          // redirected to the pricing page, but without the instance ID. I specifically
          // don't want to show an animation because in the SaaS we're also showing a
          // loading animation directly next to it. It gets a bit crowned, and it's not
          // needed.
          const { data: instanceData } = await SettingsService(
            this.$client
          ).getInstanceID()
          this.instanceId = instanceData.instance_id
        } catch (e) {}
      }
    },
    show() {
      this.selectedType = this.initialSelectedType
      modal.methods.show.bind(this)()
      this.loadInstanceID()
    },
  },
}
</script>
