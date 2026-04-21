import { defineStore } from 'pinia';

interface Asset {
  id: string;
  name: string;
  description: string;
  file_size: number;
  file_type: string;
  mime_type: string;
  owner: any;
  category?: any;
  is_public: boolean;
  is_archived: boolean;
  download_count: number;
  view_count: number;
  tags: string[];
  metadata: Record<string, any>;
  created_on: string;
  updated_on: string;
}

interface AssetCategory {
  id: string;
  name: string;
  description: string;
  color: string;
  icon: string;
  created_on: string;
}

interface AssetState {
  assets: Asset[];
  categories: AssetCategory[];
  currentAsset: Asset | null;
  loading: boolean;
  error: string | null;
  selectedAssets: Set<string>;
}

export const useAssetStore = defineStore('asset', {
  state: (): AssetState => ({
    assets: [],
    categories: [],
    currentAsset: null,
    loading: false,
    error: null,
    selectedAssets: new Set(),
  }),

  getters: {
    getAssets: (state) => state.assets,
    getCategories: (state) => state.categories,
    getCurrentAsset: (state) => state.currentAsset,
    isLoading: (state) => state.loading,
    getError: (state) => state.error,
    getSelectedAssets: (state) => Array.from(state.selectedAssets),
    getAssetById: (state) => (id: string) => {
      return state.assets.find((a) => a.id === id);
    },
    getAssetsByCategory: (state) => (categoryId: string) => {
      return state.assets.filter((a) => a.category?.id === categoryId);
    },
    getArchivedAssets: (state) => {
      return state.assets.filter((a) => a.is_archived);
    },
  },

  actions: {
    setAssets(assets: Asset[]) {
      this.assets = assets;
    },
    addAsset(asset: Asset) {
      this.assets.unshift(asset);
    },
    updateAsset(asset: Asset) {
      const index = this.assets.findIndex((a) => a.id === asset.id);
      if (index !== -1) {
        this.assets[index] = asset;
      }
    },
    removeAsset(assetId: string) {
      this.assets = this.assets.filter((a) => a.id !== assetId);
    },
    setCategories(categories: AssetCategory[]) {
      this.categories = categories;
    },
    addCategory(category: AssetCategory) {
      this.categories.push(category);
    },
    setCurrentAsset(asset: Asset | null) {
      this.currentAsset = asset;
    },
    setLoading(loading: boolean) {
      this.loading = loading;
    },
    setError(error: string | null) {
      this.error = error;
    },
    toggleAssetSelection(assetId: string) {
      if (this.selectedAssets.has(assetId)) {
        this.selectedAssets.delete(assetId);
      } else {
        this.selectedAssets.add(assetId);
      }
    },
    clearSelection() {
      this.selectedAssets.clear();
    },
    selectAll(assetIds: string[]) {
      this.selectedAssets = new Set(assetIds);
    },
  },
});
