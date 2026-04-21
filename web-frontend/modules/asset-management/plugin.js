export default defineNuxtPlugin((nuxtApp) => {
  nuxtApp.$assetService = {
    listAssets: async (workspaceId) => {
      const { $axios } = useNuxtApp();
      return $axios.$get(`/api/workspaces/${workspaceId}/assets/`);
    },
    getAsset: async (workspaceId, assetId) => {
      const { $axios } = useNuxtApp();
      return $axios.$get(`/api/workspaces/${workspaceId}/assets/${assetId}/`);
    },
    createAsset: async (workspaceId, formData) => {
      const { $axios } = useNuxtApp();
      return $axios.$post(`/api/workspaces/${workspaceId}/assets/`, formData);
    },
    updateAsset: async (workspaceId, assetId, data) => {
      const { $axios } = useNuxtApp();
      return $axios.$patch(`/api/workspaces/${workspaceId}/assets/${assetId}/`, data);
    },
    deleteAsset: async (workspaceId, assetId) => {
      const { $axios } = useNuxtApp();
      return $axios.$delete(`/api/workspaces/${workspaceId}/assets/${assetId}/`);
    },
    downloadAsset: async (workspaceId, assetId) => {
      const { $axios } = useNuxtApp();
      return $axios.$post(`/api/workspaces/${workspaceId}/assets/${assetId}/download/`);
    },
    uploadVersion: async (workspaceId, assetId, formData) => {
      const { $axios } = useNuxtApp();
      return $axios.$post(
        `/api/workspaces/${workspaceId}/assets/${assetId}/upload_version/`,
        formData
      );
    },
    getVersions: async (workspaceId, assetId) => {
      const { $axios } = useNuxtApp();
      return $axios.$get(`/api/workspaces/${workspaceId}/assets/${assetId}/versions/`);
    },
    rollbackVersion: async (workspaceId, assetId, versionId) => {
      const { $axios } = useNuxtApp();
      return $axios.$post(
        `/api/workspaces/${workspaceId}/assets/${assetId}/rollback_version/`,
        { version_id: versionId }
      );
    },
    listCategories: async (workspaceId) => {
      const { $axios } = useNuxtApp();
      return $axios.$get(`/api/workspaces/${workspaceId}/asset-categories/`);
    },
    createCategory: async (workspaceId, data) => {
      const { $axios } = useNuxtApp();
      return $axios.$post(`/api/workspaces/${workspaceId}/asset-categories/`, data);
    },
    getPermissions: async (workspaceId, assetId) => {
      const { $axios } = useNuxtApp();
      return $axios.$get(`/api/workspaces/${workspaceId}/assets/${assetId}/permissions/`);
    },
    grantPermission: async (workspaceId, assetId, userId, role) => {
      const { $axios } = useNuxtApp();
      return $axios.$post(
        `/api/workspaces/${workspaceId}/assets/${assetId}/permissions/grant/`,
        { user_id: userId, role }
      );
    },
    createShare: async (workspaceId, assetId, data) => {
      const { $axios } = useNuxtApp();
      return $axios.$post(
        `/api/workspaces/${workspaceId}/assets/${assetId}/shares/create_share/`,
        data
      );
    },
    getShares: async (workspaceId, assetId) => {
      const { $axios } = useNuxtApp();
      return $axios.$get(`/api/workspaces/${workspaceId}/assets/${assetId}/shares/`);
    },
  };
});
