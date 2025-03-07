import json

from django.core.files.base import ContentFile

from baserow.contrib.database.file_import.models import FileImportJob

data = [["test-1"]]


class FileImportFixtures:
    def create_file_import_job(self, **kwargs):
        if "user" not in kwargs:
            kwargs["user"] = self.create_user()

        if "database" not in kwargs:
            kwargs["database"] = self.create_database_application(user=kwargs["user"])

        if "name" not in kwargs:
            kwargs["name"] = self.fake.name()

        if "first_row_header" not in kwargs:
            kwargs["first_row_header"] = True

        if "data" not in kwargs:
            data = []
            row_count = kwargs.pop("row_count", 5)
            column_count = kwargs.pop("column_count", 2)
            if kwargs["first_row_header"]:
                columns = [f"Column {i}" for i in range(column_count)]
                data.append(columns)
            for index in range(row_count):
                row = []
                for field_index in range(column_count):
                    row.append(f"data_{index}_{field_index}")
                data.append(row)
            data = {"data": data}
        else:
            data = kwargs.pop("data")

        data_file = kwargs.get("data_file", ContentFile(json.dumps(data)))

        job = FileImportJob.objects.create(**kwargs)

        job.data_file.save(None, data_file)

        return job
