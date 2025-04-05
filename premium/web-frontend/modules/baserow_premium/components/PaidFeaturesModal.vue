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
      <MarkdownIt :content="content" />
      <div>
        <Button
          type="primary"
          size="large"
          href="https://baserow.io/pricing"
          target="_blank"
          tag="a"
          >{{ $t('premiumModal.viewPricing') }}</Button
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
    }
  },
  computed: {
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
    name() {
      return this.selectedPaidFeature.getName()
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
    show() {
      this.selectedType = this.initialSelectedType
      modal.methods.show.bind(this)()
    },
  },
}
</script>
