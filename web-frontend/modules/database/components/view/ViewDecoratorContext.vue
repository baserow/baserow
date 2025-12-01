<template>
  <Context max-height-if-outside-viewport>
    <ViewDecoratorList
      v-if="activeDecorations.length === 0"
      :database="database"
      :view="view"
      @select="addDecoration($event)"
    />
    <div v-else class="decorator-context">
      <div v-auto-overflow-scroll class="decorator-context__list">
        <div
          v-for="dec in activeDecorations"
          :key="dec.decoration.id"
          class="decorator-context__decorator"
        >
          <div class="decorator-context__decorator-header">
            <div class="decorator-context__decorator-header-info">
              <ViewDecoratorItem :decorator-type="dec.decoratorType" />
            </div>
            <div
              v-show="dec.valueProviderType"
              class="decorator-context__decorator-header-select"
            >
              <Picker
                v-if="dec.valueProviderType"
                :icon="dec.valueProviderType.getIconClass()"
                :name="dec.valueProviderType.getName()"
                small
                @select="selectValueProvider(dec.decoration, $event)"
              >
                <template #default="{ hidePicker }">
                  <div
                    class="decorator-context__decorator-value-provider-select-list"
                  >
                    <DecoratorValueProviderList
                      :decoration="dec.decoration"
                      @select="
                        ;[
                          selectValueProvider(dec.decoration, $event),
                          hidePicker(),
                        ]
                      "
                    />
                  </div>
                </template>
              </Picker>
            </div>
            <div class="decorator-context__decorator-header-trash">
              <ButtonIcon
                icon="iconoir-bin"
                @click="removeDecoration(dec.decoration)"
              ></ButtonIcon>
            </div>
          </div>
          <component
            :is="dec.valueProviderType.getFormComponent()"
            v-if="dec.valueProviderType"
            :view="view"
            :table="table"
            :database="database"
            :fields="fields"
            :read-only="readOnly"
            :options="dec.decoration.value_provider_conf"
            @update="updateDecorationOptions(dec.decoration, $event)"
          />
          <DecoratorValueProviderList
            v-else
            :decoration="dec.decoration"
            :direction="'row'"
            :read-only="readOnly || dec.decoration._.loading"
            @select="selectValueProvider(dec.decoration, $event)"
          />
        </div>
      </div>
      <div ref="addDecoratorLink" class="context__footer">
        <ButtonText
          icon="iconoir-plus"
          class="choose-select-field__link margin-right-auto"
          @click="
            $refs.selectDecoratorContext.toggle(
              $refs.addDecoratorLink,
              'bottom',
              'left',
              1
            )
          "
        >
          {{ $t('viewDecoratorContext.addDecorator') }}
        </ButtonText>
        <SelectViewDecoratorContext
          ref="selectDecoratorContext"
          :database="database"
          :view="view"
          @select="
            ;[$refs.selectDecoratorContext.hide(), addDecoration($event)]
          "
        />
      </div>
    </div>
  </Context>
</template>

<script>
import context from '@baserow/modules/core/mixins/context'
import viewDecoration from '@baserow/modules/database/mixins/viewDecoration'
import ViewDecoratorList from '@baserow/modules/database/components/view/ViewDecoratorList'
import ViewDecoratorItem from '@baserow/modules/database/components/view/ViewDecoratorItem'
import SelectViewDecoratorContext from '@baserow/modules/database/components/view/SelectViewDecoratorContext'
import DecoratorValueProviderItem from '@baserow/modules/database/components/view/DecoratorValueProviderItem'
import DecoratorValueProviderList from '@baserow/modules/database/components/view/DecoratorValueProviderList'
import { notifyIf } from '@baserow/modules/core/utils/error'

export default {
  name: 'ViewDecoratorContext',
  components: {
    ViewDecoratorList,
    ViewDecoratorItem,
    DecoratorValueProviderItem,
    SelectViewDecoratorContext,
    DecoratorValueProviderList,
  },
  mixins: [context, viewDecoration],
  props: {
    database: {
      type: Object,
      required: true,
    },
    fields: {
      type: Array,
      required: true,
    },
    view: {
      type: Object,
      required: true,
    },
    table: {
      type: Object,
      required: true,
    },
    readOnly: {
      type: Boolean,
      required: true,
    },
  },
  methods: {
    async removeDecoration(decoration) {
      try {
        await this.$store.dispatch('view/deleteDecoration', {
          view: this.view,
          decoration,
          readOnly: this.readOnly,
        })
      } catch (error) {
        notifyIf(error, 'view')
      }
    },
    async selectValueProvider(decoration, valueProvider) {
      const valueProviderType = this.$registry.get(
        'decoratorValueProvider',
        valueProvider
      )
      try {
        await this.$store.dispatch('view/updateDecoration', {
          view: this.view,
          values: {
            value_provider_type: valueProviderType.getType(),
            value_provider_conf: valueProviderType.getDefaultConfiguration({
              view: this.view,
              fields: this.fields,
            }),
          },
          decoration,
          readOnly: this.readOnly,
        })
      } catch (error) {
        notifyIf(error, 'view')
      }
    },
    async addDecoration(decoratorType) {
      const decoration = {
        type: decoratorType.getType(),
        value_provider_type: '',
        value_provider_conf: {},
      }
      try {
        await this.$store.dispatch('view/createDecoration', {
          view: this.view,
          values: decoration,
          readOnly: this.readOnly,
        })
      } catch (error) {
        notifyIf(error, 'view')
      }
    },
    async updateDecorationOptions(decoration, options) {
      try {
        await this.$store.dispatch('view/updateDecoration', {
          view: this.view,
          values: { value_provider_conf: options },
          decoration,
          readOnly: this.readOnly,
        })
      } catch (error) {
        notifyIf(error, 'view')
      }
    },
  },
}
</script>
