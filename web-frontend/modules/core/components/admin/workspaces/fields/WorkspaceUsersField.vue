<script>
import UserWorkspacesField from '@baserow/modules/core/components/admin/users/fields/UserWorkspacesField'

export default {
  name: 'WorkspaceUsersField',
  extends: UserWorkspacesField,
  data() {
    return {
      nameKey: 'email',
    }
  },
}
</script>
