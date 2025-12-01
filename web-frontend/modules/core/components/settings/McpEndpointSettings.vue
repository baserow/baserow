<template>
  <div>
    <template v-if="page === 'list'">
      <h2 class="box__title">{{ $t('mcpEndpointSettings.title') }}</h2>
      <div class="align-right">
        <a class="button button--primary" @click.prevent="page = 'create'">
          {{ $t('mcpEndpointSettings.createEndpoint') }}
          <i class="iconoir-plus"></i>
        </a>
      </div>
      <Error :error="error"></Error>
      <div v-if="listLoading" class="loading"></div>
      <div v-else>
        <p v-if="endpoints.length === 0" class="margin-top-3">
          {{ $t('mcpEndpointSettings.noEndpointsMessage') }}
        </p>
        <McpEndpoint
          v-for="endpoint in endpoints"
          :key="endpoint.id"
          :endpoint="endpoint"
          @deleted="deleteEndpoint(endpoint.id)"
        ></McpEndpoint>
      </div>
    </template>
    <template v-else-if="page === 'create'">
      <h2 class="box__title">{{ $t('mcpEndpointSettings.createNewTitle') }}</h2>
      <Error :error="error"></Error>
      <McpEndpointForm @submitted="create">
        <div class="actions">
          <ul class="action__links">
            <li>
              <a @click.prevent="page = 'list'">
                <i class="iconoir-arrow-left"></i>
                {{ $t('mcpEndpointSettings.backToOverview') }}
              </a>
            </li>
          </ul>
          <Button
            type="primary"
            size="large"
            :loading="createLoading"
            :disabled="createLoading"
          >
            {{ $t('mcpEndpointSettings.createEndpoint') }}
          </Button>
        </div>
      </McpEndpointForm>
    </template>
  </div>
</template>

<script>
import error from '@baserow/modules/core/mixins/error'
import McpEndpointForm from '@baserow/modules/core/components/settings/McpEndpointForm'
import McpEndpoint from '@baserow/modules/core/components/settings/McpEndpoint'
import McpEndpointService from '@baserow/modules/core/services/mcpEndpoint'

export default {
  name: 'McpEndpointSettings',
  components: { McpEndpoint, McpEndpointForm },
  mixins: [error],
  data() {
    return {
      page: 'list',
      endpoints: [],
      listLoading: true,
      createLoading: false,
    }
  },
  /**
   * When the component is mounted we immediately want to fetch all the endpoints, so
   * that they can be displayed to the user.
   */
  async mounted() {
    try {
      const { data } = await McpEndpointService(this.$client).fetchAll()
      this.endpoints = data
      this.listLoading = false
    } catch (error) {
      this.listLoading = false
      this.handleError(error, 'endpoint')
    }
  },
  methods: {
    /**
     * When the create endpoint form is submitted the create method is called. It will
     * make a request to the backend asking to create a new endpoint. The newly created
     * endpoint is going to be added last.
     */
    async create(values) {
      this.createLoading = true
      this.hideError()

      try {
        const { data } = await McpEndpointService(this.$client).create(values)
        this.endpoints.push(data)
        this.createLoading = false
        this.page = 'list'
      } catch (error) {
        this.createLoading = false
        this.handleError(error, 'endpoint')
      }
    },
    /**
     * Called when a endpoint is already deleted. It must then be removed from the
     * list of endpoints.
     */
    deleteEndpoint(endpointId) {
      const index = this.endpoints.findIndex(
        (endpoint) => endpoint.id === endpointId
      )
      this.endpoints.splice(index, 1)
    },
  },
}
</script>
