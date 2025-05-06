<template>
  <div class="chat">
    <Chat
      :api-key="key"
      :initial-messages="initialMessages"
      :tools="tools"
      :tool-handlers="toolHandlers"
    />
  </div>
</template>

<script>
import Chat from '@baserow/modules/core/components/sidebar/Chat'
import { mapGetters, mapState } from 'vuex'

export default {
  name: 'ChatWrapper',
  components: { Chat },
  mixins: [],
  props: {},
  data() {
    return {
      shouldShow: false,
      key: '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',
    }
  },
  computed: {
    ...mapGetters({
      applications: 'application/getAll',
      userName: 'auth/getName',
      workspace: 'workspace/getSelected',
    }),
    appList() {
      return this.applications.map(({ name, type }) => {
        return `- ${name} (${type})`
      })
    },
    initialMessages() {
      return [
        {
          role: 'system',
          content: `You are a friendly and concise Baserow assistant.
            You help the user to design a database with table and fields.
            <user> name is ${this.userName}.

            In the current workspace there is this list of databases and applications:

            ${this.appList.join('\n')}`,
        },
      ]
    },
    tools() {
      return [
        {
          type: 'function',
          function: {
            name: 'get_current_time',
            description: 'Returns the current time in ISO format',
            parameters: {
              type: 'object',
              properties: {},
              required: [],
            },
          },
        },
        {
          type: 'function',
          function: {
            name: 'create_database',
            description: 'Creates a new Baserow database',
            parameters: {
              type: 'object',
              properties: {
                name: {
                  type: 'string',
                  description: 'Name of the database to create',
                },
              },
              required: ['name'],
            },
          },
        },
      ]
    },
    toolHandlers() {
      return {
        get_current_time: () => {
          return new Date().toISOString()
        },
        create_database: async ({ name }) => {
          console.log('call create', name)
          try {
            const application = await this.$store.dispatch(
              'application/create',
              {
                type: 'database',
                workspace: this.workspace,
                values: { name },
              }
            )
            // select the application just created in the sidebar and open it
            await this.$store.dispatch('application/selectById', application.id)
            await this.$registry
              .get('application', application.type)
              .select(application, this)
            return 'Application created successfully'
          } catch (error) {
            console.log(error)
            return "An error happened, the database couldn't be created"
          }
        },
      }
    },
  },
  methods: {},
}

// Could you create a database with name Test
</script>
<style scoped>
.chat {
  display: flex;
  flex-direction: column;
  height: 100%;
}
</style>
