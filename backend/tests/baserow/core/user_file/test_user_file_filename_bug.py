"""
Test for filename-dependent upload bug where files with hyphens and numbers
fail to upload inconsistently.
"""
import pytest
from io import BytesIO
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.exceptions import ValidationError

from baserow.core.user_files.handler import UserFileHandler
from baserow.core.user_files.models import UserFile
from baserow.core.user_files.exceptions import InvalidUserFileNameError
from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.fields.handler import FieldHandler


@pytest.mark.django_db
def test_upload_files_with_hyphens_and_numbers(data_fixture):
    """
    Test that files with hyphens and numbers in their names can be uploaded
    and used in file fields without errors.
    
    This test reproduces the bug where "Blobs-1.png" fails but "Blobs-2.png" succeeds.
    """
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field_handler = FieldHandler()
    row_handler = RowHandler()
    user_file_handler = UserFileHandler()
    
    # Create a file field
    file_field = field_handler.create_field(
        user=user, table=table, type_name="file", name="File"
    )
    
    # Test filenames that should all work
    test_filenames = [
        "Blobs-1.png",
        "Blobs-2.png",
        "Blobs1.png",
        "Blobs2.png",
        "test-file-1.jpg",
        "document-v2.pdf",
        "image-final-3.png",
        "report-2024-01.xlsx",
    ]
    
    model = table.get_model(attribute_names=True)
    uploaded_files = []
    
    # Upload all files
    for filename in test_filenames:
        content = f"test content for {filename}".encode()
        file_stream = BytesIO(content)
        file_stream.name = filename
        
        # Upload the file
        user_file = user_file_handler.upload_user_file(user, filename, file_stream)
        uploaded_files.append(user_file)
        
        # Verify the file was created
        assert user_file.original_name == filename
        assert user_file.name  # Should have a generated name
        # Verify the generated name matches the expected format
        assert "_" in user_file.name
        assert "." in user_file.name
    
    # Now try to create rows with each uploaded file
    for user_file in uploaded_files:
        row = row_handler.create_row(
            user=user,
            table=table,
            values={"file": [{"name": user_file.name}]},
            model=model,
        )
        
        # Verify the row was created successfully
        assert len(row.file) == 1
        assert row.file[0]["visible_name"] == user_file.original_name
        assert row.file[0]["name"] == user_file.name


@pytest.mark.django_db
def test_file_field_with_hyphenated_filenames_in_form(data_fixture, api_client):
    """
    Test that form submissions with file fields work correctly for files
    with hyphens and numbers in their original names.
    """
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field_handler = FieldHandler()
    user_file_handler = UserFileHandler()
    
    # Create a file field
    file_field = field_handler.create_field(
        user=user, table=table, type_name="file", name="Attachment"
    )
    
    # Create a form view
    form = data_fixture.create_form_view(table=table, public=True)
    data_fixture.create_form_view_field_option(form, file_field, enabled=True)
    
    # Upload files with problematic names
    test_files = [
        ("Blobs-1.png", b"fake png content 1"),
        ("Blobs-2.png", b"fake png content 2"),
        ("document-v1.pdf", b"fake pdf content"),
    ]
    
    uploaded_file_names = []
    for filename, content in test_files:
        file_stream = BytesIO(content)
        file_stream.name = filename
        user_file = user_file_handler.upload_user_file(user, filename, file_stream)
        uploaded_file_names.append(user_file.name)
    
    # Submit form with each file
    from django.urls import reverse
    url = reverse("api:database:views:form:submit", kwargs={"slug": form.slug})
    
    for file_name in uploaded_file_names:
        response = api_client.post(
            url,
            {f"field_{file_field.id}": [{"name": file_name}]},
            format="json",
        )
        
        # Should succeed for all files
        assert response.status_code == 200, f"Failed for file: {file_name}. Response: {response.json()}"
        assert response.json()["row_id"] is not None


@pytest.mark.django_db
def test_user_file_deconstruct_name_with_various_formats(data_fixture):
    """
    Test that UserFile.deconstruct_name handles various filename formats correctly.
    """
    # Valid generated filenames should work
    valid_names = [
        "abc123_def456.png",
        "ABC123_DEF456.jpg",
        "a1b2c3_d4e5f6.pdf",
        "randomUnique_sha256hash.txt",
    ]
    
    for name in valid_names:
        result = UserFile.deconstruct_name(name)
        assert "unique" in result
        assert "sha256_hash" in result
        assert "original_extension" in result


@pytest.mark.django_db
def test_file_field_rejects_original_filenames_with_clear_error(data_fixture):
    """
    Test that when a user tries to use an original filename (like "Blobs-1.png")
    instead of the generated name, they get a clear error message.
    """
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field_handler = FieldHandler()
    row_handler = RowHandler()
    
    # Create a file field
    file_field = field_handler.create_field(
        user=user, table=table, type_name="file", name="File"
    )
    
    model = table.get_model(attribute_names=True)
    
    # Try to create a row with an original filename (not a generated name)
    with pytest.raises(ValidationError) as exc_info:
        row_handler.create_row(
            user=user,
            table=table,
            values={"file": [{"name": "Blobs-1.png"}]},
            model=model,
        )
    
    # Verify the error message is helpful
    error_message = str(exc_info.value)
    assert "Blobs-1.png" in error_message
    assert "format" in error_message.lower()


@pytest.mark.django_db
def test_deconstruct_name_provides_helpful_error_for_invalid_names():
    """
    Test that deconstruct_name provides helpful error messages for invalid names.
    """
    invalid_names = [
        "Blobs-1.png",  # Original filename with hyphen
        "test file.jpg",  # Filename with space
        "document.pdf",  # No underscore
        "_hash.png",  # Missing unique part
        "unique_.png",  # Missing hash part
    ]
    
    for invalid_name in invalid_names:
        with pytest.raises(InvalidUserFileNameError) as exc_info:
            UserFile.deconstruct_name(invalid_name)
        
        error = exc_info.value
        assert error.name == invalid_name
        assert "format" in str(error).lower()
        assert "unique_hash.extension" in str(error) or "alphanumeric" in str(error).lower()
