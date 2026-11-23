class DataSyncExportSerializedStructure:
    @staticmethod
    def data_sync(id, type_name, last_sync, last_error, properties, **type_specific):
        return {
            "id": id,
            "type": type_name,
            "last_sync": last_sync,
            "last_error": last_error,
            "properties": properties,
            **type_specific,
        }

    @staticmethod
    def property(key, field_id, unique_primary, metadata):
        return {
            "key": key,
            "field_id": field_id,
            "unique_primary": unique_primary,
            "metadata": metadata,
        }
