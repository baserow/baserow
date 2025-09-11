<template>
  <Context overflow-scroll max-height-if-outside-viewport>
    <ul class="context__menu">
      <li
        v-if="
          $hasPermission(
            'database.table.create_row',
            table,
            database.workspace.id
          ) ||
          $hasPermission(
            'database.table.view.create_row',
            view,
            database.workspace.id
          )
        "
        class="context__menu-item"
      >
        <a
          class="context__menu-item-link"
          @click=";[$emit('create-row'), hide()]"
        >
          <i class="context__menu-item-icon iconoir-plus"></i>
          {{ $t('kanbanViewStackContext.createCard') }}
        </a>
      </li>
      <li
        v-if="
          option !== null &&
          !singleSelectField.immutable_properties &&
          $hasPermission(
            'database.table.field.update',
            singleSelectField,
            database.workspace.id
          )
        "
        class="context__menu-item"
      >
        <a
          ref="updateContextLink"
          class="context__menu-item-link"
          @click="$refs.updateContext.toggle($refs.updateContextLink)"
        >
          <i class="context__menu-item-icon iconoir-edit-pencil"></i>
          {{ $t('kanbanViewStackContext.editStack') }}
        </a>
        <KanbanViewUpdateStackContext
          ref="updateContext"
          :option="option"
          :fields="fields"
          :store-prefix="storePrefix"
          @saved="hide()"
        ></KanbanViewUpdateStackContext>
      </li>
      <li
        v-if="
          option !== null &&
          !singleSelectField.immutable_properties &&
          $hasPermission(
            'database.table.field.update',
            singleSelectField,
            database.workspace.id
          )
        "
        class="context__menu-item context__menu-item--with-separator"
      >
        <a
          class="context__menu-item-link context__menu-item-link--delete"
          @click="$refs.deleteModal.show()"
        >
          <i class="context__menu-item-icon iconoir-bin"></i>
          {{ $t('kanbanViewStackContext.deleteStack') }}
        </a>
      </li>
    </ul>
    <Modal v-if="option !== null" ref="deleteModal">
      <h2 class="box__title">
        {{ $t('kanbanViewStackContext.delete', { name: option.value }) }}
      </h2>
      <Error :error="error"></Error>
      <div>
        <p>
          {{
            $t('kanbanViewStackContext.deleteDescription', {
              name: option.value,
            })
          }}
        </p>
        <div class="actions">
          <div class="align-right">
            <Button
              type="danger"
              size="large"
              :disabled="loading"
              :loading="loading"
              @click="deleteStack()"
            >
              {{ $t('kanbanViewStackContext.delete', { name: option.value }) }}
            </Button>
          </div>
        </div>
      </div>
    </Modal>
  </Context>
</template>

<script>
import context from '@baserow/modules/core/mixins/context'
import error from '@baserow/modules/core/mixins/error'
import KanbanViewUpdateStackContext from '@baserow_premium/components/views/kanban/KanbanViewUpdateStackContext'

export default {
  name: 'KanbanViewStackContext',
  components: { KanbanViewUpdateStackContext },
  mixins: [context, error],
  props: {
    option: {
      validator: (prop) => typeof prop === 'object' || prop === null,
      required: true,
    },
    database: {
      type: Object,
      required: true,
    },
    table: {
      type: Object,
      required: true,
    },
    view: {
      type: Object,
      required: true,
    },
    fields: {
      type: Array,
      required: true,
    },
    singleSelectField: {
      type: Object,
      required: false,
      default: null,
    },
    storePrefix: {
      type: String,
      required: true,
    },
  },
  data() {
    return {
      loading: false,
    }
  },
  methods: {
    async deleteStack() {
      this.loading = true

      try {
        const doUpdate = await this.$store.dispatch(
          this.storePrefix + 'view/kanban/deleteStack',
          {
            optionId: this.option.id,
            singleSelectField: this.singleSelectField,
            deferredFieldUpdate: true,
          }
        )
        await this.$emit('refresh', {
          callback: () => {
            doUpdate()
            this.loading = false
          },
        })
      } catch (error) {
        this.handleError(error)
        this.loading = false
      }
    },
  },
}
</script>
