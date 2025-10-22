<template>
  <form @submit.prevent @keydown.enter.prevent>
    <FormGroup
      small-label
      :label="$t('routerForm.defaultEdgeLabelLabel')"
      required
      class="margin-bottom-2"
    >
      <p class="margin-top-0 margin-bottom-1">
        {{ $t('routerForm.defaultEdgeLabelDescription') }}
      </p>
      <FormInput
        v-model="values.default_edge_label"
        :placeholder="$t('nodeType.routerDefaultEdgeLabelFallback')"
      />
    </FormGroup>
    <FormSection
      class="margin-bottom-2"
      :title="$t('routerForm.branchesHeading')"
      ><p class="margin-top-0 margin-bottom-1">
        {{ $t('routerForm.branchesDescription') }}
      </p>
      <div>
        <SidebarExpandable
          v-for="(edge, index) in v$.values.edges.$model"
          :key="edge.uid"
          v-sortable="{
            id: edge.uid,
            update: orderEdges,
            enabled: true,
            handle: '[data-sortable-handle]',
          }"
          :default-expanded="index === 0"
          toggle-on-click
        >
          <template #title>
            <span v-if="edge.label">{{ edge.label }}</span>
            <span v-else class="color-neutral"
              >({{ $t('routerForm.noLabel') }})</span
            >
            <Icon
              v-if="getEdgeErrorMessage(edge)"
              :key="getEdgeErrorMessage(edge)"
              v-tooltip="getEdgeErrorMessage(edge)"
              icon="iconoir-warning-circle"
              size="medium"
              type="error"
            />
          </template>
          <template #default>
            <FormGroup
              small-label
              horizontal
              required
              class="margin-bottom-2"
              :label="$t('routerForm.branchLabel')"
              :error-message="
                v$.values.edges.$each.$response?.$errors[index]?.label[0]
                  ?.$message
              "
            >
              <FormInput v-model="v$.values.edges.$model[index].label">
              </FormInput>
            </FormGroup>
            <FormGroup
              small-label
              horizontal
              required
              class="margin-bottom-2"
              :label="$t('routerForm.branchConditionLabel')"
            >
              <InjectedFormulaInput
                v-model="v$.values.edges.$model[index].condition"
                :placeholder="$t('routerForm.branchConditionPlaceholder')"
              />
            </FormGroup>
          </template>
          <template #footer>
            <ButtonText
              :key="edgeDeletionTooltip(edge)"
              v-tooltip="edgeDeletionTooltip(edge)"
              tooltip-position="bottom-left"
              :disabled="!edgeCanBeDeleted(edge)"
              icon="iconoir-bin"
              @click="removeEdge(edge)"
            >
              {{ $t('action.delete') }}
            </ButtonText>
          </template>
        </SidebarExpandable>
      </div>
      <ButtonText
        type="primary"
        icon="iconoir-plus"
        size="small"
        @click="addEdge"
      >
        {{ $t('routerForm.addEdge') }}
      </ButtonText>
    </FormSection>
  </form>
</template>

<script>
import form from '@baserow/modules/core/mixins/form'
import InjectedFormulaInput from '@baserow/modules/core/components/formula/InjectedFormulaInput'
import SidebarExpandable from '@baserow/modules/builder/components/SidebarExpandable.vue'
import {
  getNextAvailableNameInSequence,
  uuid,
} from '@baserow/modules/core/utils/string'
import { useVuelidate } from '@vuelidate/core'
import { helpers, maxLength, minLength, required } from '@vuelidate/validators'

export default {
  name: 'CoreRouterServiceForm',
  components: {
    SidebarExpandable,
    InjectedFormulaInput,
  },
  mixins: [form],
  props: {
    application: {
      type: Object,
      required: false,
      default: null,
    },
    service: {
      type: Object,
      required: false,
      default: null,
    },
    edgeInUseFn: {
      type: Function,
      required: false,
      default: () => () => false,
    },
  },
  setup() {
    return { v$: useVuelidate() }
  },
  data() {
    return {
      allowedValues: ['default_edge_label', 'edges'],
      values: {
        default_edge_label: '',
        edges: [],
      },
    }
  },
  computed: {
    serviceType() {
      return this.$registry.get('service', 'router')
    },
  },
  methods: {
    addEdge() {
      this.v$.values.edges.$model.push({
        label: getNextAvailableNameInSequence(
          this.$t('routerForm.edgeDefaultName'),
          this.v$.values.edges.$model.map(({ label }) => label)
        ),
        condition: { formula: '', mode: 'simple' },
        uid: uuid(),
      })
    },
    orderEdges(newOrder) {
      const edgeByUid = Object.fromEntries(
        this.v$.values.edges.$model.map((edge) => [edge.uid, edge])
      )
      this.v$.values.edges.$model = newOrder.map(
        (edgeUid) => edgeByUid[edgeUid]
      )
    },
    removeEdge(edge) {
      this.v$.values.edges.$model = this.v$.values.edges.$model.filter(
        (item) => item !== edge
      )
    },
    edgeCanBeDeleted(edge) {
      return this.v$.values.edges.$model.length > 1 && !this.edgeInUseFn(edge)
    },
    edgeDeletionTooltip(edge) {
      if (this.v$.values.edges.$model.length === 1) {
        return this.$t('routerForm.edgeDeletionLastEdge')
      } else if (this.edgeInUseFn(edge)) {
        return this.$t('routerForm.edgeDeletionHasOutput')
      }
      return null
    },
    getEdgeErrorMessage(edge) {
      return this.serviceType.getEdgeErrorMessage(edge)
    },
  },
  validations() {
    return {
      values: {
        edges: {
          minLength: 1,
          maxLength: 5,
          $each: helpers.forEach({
            label: {
              required,
              minLength: helpers.withMessage(
                this.$t('error.minMaxLength', {
                  max: 50,
                  min: 2,
                }),
                minLength(2)
              ),
              maxLength: helpers.withMessage(
                this.$t('error.minMaxLength', {
                  max: 50,
                  min: 2,
                }),
                maxLength(50)
              ),
            },
          }),
        },
      },
    }
  },
}
</script>
