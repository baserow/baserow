from datetime import datetime, timedelta, timezone

import pytest

from baserow_enterprise.assistant.handler import AssistantHandler
from baserow_enterprise.assistant.models import (
    AssistantChat,
    AssistantChatMessage,
    AssistantChatPrediction,
)


@pytest.mark.django_db
def test_delete_predictions_removes_old_unrated_predictions(enterprise_data_fixture):
    """Test that old predictions without sentiment are deleted."""

    user = enterprise_data_fixture.create_user()
    workspace = enterprise_data_fixture.create_workspace(user=user)

    # Create a chat
    chat = AssistantChat.objects.create(user=user, workspace=workspace)

    # Create old predictions (older than 30 days) without sentiment
    old_date = datetime.now(timezone.utc) - timedelta(days=35)

    human_msg_1 = AssistantChatMessage.objects.create(
        chat=chat, role="human", content="Question 1", created_on=old_date
    )
    ai_msg_1 = AssistantChatMessage.objects.create(
        chat=chat, role="ai", content="Answer 1", created_on=old_date
    )
    prediction_1 = AssistantChatPrediction.objects.create(
        human_message=human_msg_1,
        ai_response=ai_msg_1,
        prediction={"test": "data"},
    )
    prediction_1.created_on = old_date
    prediction_1.save()

    human_msg_2 = AssistantChatMessage.objects.create(
        chat=chat, role="human", content="Question 2", created_on=old_date
    )
    ai_msg_2 = AssistantChatMessage.objects.create(
        chat=chat, role="ai", content="Answer 2", created_on=old_date
    )
    prediction_2 = AssistantChatPrediction.objects.create(
        human_message=human_msg_2,
        ai_response=ai_msg_2,
        prediction={"test": "data"},
    )
    prediction_2.created_on = old_date
    prediction_2.save()

    # Delete predictions older than 30 days
    handler = AssistantHandler()
    deleted_count, _ = handler.delete_predictions(older_than_days=30)

    # Both predictions should be deleted
    assert deleted_count == 2
    assert AssistantChatPrediction.objects.count() == 0


@pytest.mark.django_db
def test_delete_predictions_preserves_recent_predictions(enterprise_data_fixture):
    """Test that recent predictions are not deleted."""

    user = enterprise_data_fixture.create_user()
    workspace = enterprise_data_fixture.create_workspace(user=user)

    chat = AssistantChat.objects.create(user=user, workspace=workspace)

    # Create recent prediction (within 30 days)
    recent_date = datetime.now(timezone.utc) - timedelta(days=10)

    human_msg = AssistantChatMessage.objects.create(
        chat=chat, role="human", content="Question", created_on=recent_date
    )
    ai_msg = AssistantChatMessage.objects.create(
        chat=chat, role="ai", content="Answer", created_on=recent_date
    )
    prediction = AssistantChatPrediction.objects.create(
        human_message=human_msg,
        ai_response=ai_msg,
        prediction={"test": "data"},
    )
    prediction.created_on = recent_date
    prediction.save()

    handler = AssistantHandler()
    deleted_count, _ = handler.delete_predictions(older_than_days=30)

    # Prediction should NOT be deleted
    assert deleted_count == 0
    assert AssistantChatPrediction.objects.count() == 1


@pytest.mark.django_db
def test_delete_predictions_excludes_rated_by_default(enterprise_data_fixture):
    """
    Test that predictions with sentiment are excluded from deletion by default.
    """

    user = enterprise_data_fixture.create_user()
    workspace = enterprise_data_fixture.create_workspace(user=user)

    chat = AssistantChat.objects.create(user=user, workspace=workspace)
    old_date = datetime.now(timezone.utc) - timedelta(days=35)

    # Create old prediction with LIKE sentiment
    human_msg_1 = AssistantChatMessage.objects.create(
        chat=chat, role="human", content="Question 1", created_on=old_date
    )
    ai_msg_1 = AssistantChatMessage.objects.create(
        chat=chat, role="ai", content="Answer 1", created_on=old_date
    )
    prediction_1 = AssistantChatPrediction.objects.create(
        human_message=human_msg_1,
        ai_response=ai_msg_1,
        prediction={"test": "data"},
        human_sentiment=AssistantChatPrediction.SENTIMENT_MAP["LIKE"],
    )
    prediction_1.created_on = old_date
    prediction_1.save()

    # Create old prediction with DISLIKE sentiment
    human_msg_2 = AssistantChatMessage.objects.create(
        chat=chat, role="human", content="Question 2", created_on=old_date
    )
    ai_msg_2 = AssistantChatMessage.objects.create(
        chat=chat, role="ai", content="Answer 2", created_on=old_date
    )
    prediction_2 = AssistantChatPrediction.objects.create(
        human_message=human_msg_2,
        ai_response=ai_msg_2,
        prediction={"test": "data"},
        human_sentiment=AssistantChatPrediction.SENTIMENT_MAP["DISLIKE"],
    )
    prediction_2.created_on = old_date
    prediction_2.save()

    handler = AssistantHandler()
    deleted_count, _ = handler.delete_predictions(
        older_than_days=30, exclude_rated=True
    )

    # No predictions should be deleted (both have sentiment)
    assert deleted_count == 0
    assert AssistantChatPrediction.objects.count() == 2


@pytest.mark.django_db
def test_delete_predictions_includes_rated_when_specified(enterprise_data_fixture):
    """
    Test that predictions with sentiment are deleted when exclude_rated=False.
    """

    user = enterprise_data_fixture.create_user()
    workspace = enterprise_data_fixture.create_workspace(user=user)

    chat = AssistantChat.objects.create(user=user, workspace=workspace)
    old_date = datetime.now(timezone.utc) - timedelta(days=35)

    # Create old prediction with sentiment
    human_msg = AssistantChatMessage.objects.create(
        chat=chat, role="human", content="Question", created_on=old_date
    )
    ai_msg = AssistantChatMessage.objects.create(
        chat=chat, role="ai", content="Answer", created_on=old_date
    )
    prediction = AssistantChatPrediction.objects.create(
        human_message=human_msg,
        ai_response=ai_msg,
        prediction={"test": "data"},
        human_sentiment=AssistantChatPrediction.SENTIMENT_MAP["LIKE"],
        human_feedback="Great answer!",
    )
    prediction.created_on = old_date
    prediction.save()

    handler = AssistantHandler()
    deleted_count, _ = handler.delete_predictions(
        older_than_days=30, exclude_rated=False
    )

    # Prediction should be deleted even with sentiment
    assert deleted_count == 1
    assert AssistantChatPrediction.objects.count() == 0


@pytest.mark.django_db
def test_delete_predictions_handles_mixed_scenarios(enterprise_data_fixture):
    """
    Test deletion with mixed old/recent and rated/unrated predictions.
    """

    user = enterprise_data_fixture.create_user()
    workspace = enterprise_data_fixture.create_workspace(user=user)

    chat = AssistantChat.objects.create(user=user, workspace=workspace)
    old_date = datetime.now(timezone.utc) - timedelta(days=35)
    recent_date = datetime.now(timezone.utc) - timedelta(days=10)

    # Old + unrated (should be deleted)
    human_msg_1 = AssistantChatMessage.objects.create(
        chat=chat, role="human", content="Q1", created_on=old_date
    )
    ai_msg_1 = AssistantChatMessage.objects.create(
        chat=chat, role="ai", content="A1", created_on=old_date
    )
    pred_1 = AssistantChatPrediction.objects.create(
        human_message=human_msg_1, ai_response=ai_msg_1, prediction={}
    )
    pred_1.created_on = old_date
    pred_1.save()

    # Old + rated (should NOT be deleted)
    human_msg_2 = AssistantChatMessage.objects.create(
        chat=chat, role="human", content="Q2", created_on=old_date
    )
    ai_msg_2 = AssistantChatMessage.objects.create(
        chat=chat, role="ai", content="A2", created_on=old_date
    )
    pred_2 = AssistantChatPrediction.objects.create(
        human_message=human_msg_2,
        ai_response=ai_msg_2,
        prediction={},
        human_sentiment=AssistantChatPrediction.SENTIMENT_MAP["LIKE"],
    )
    pred_2.created_on = old_date
    pred_2.save()

    # Recent + unrated (should NOT be deleted)
    human_msg_3 = AssistantChatMessage.objects.create(
        chat=chat, role="human", content="Q3", created_on=recent_date
    )
    ai_msg_3 = AssistantChatMessage.objects.create(
        chat=chat, role="ai", content="A3", created_on=recent_date
    )
    pred_3 = AssistantChatPrediction.objects.create(
        human_message=human_msg_3, ai_response=ai_msg_3, prediction={}
    )
    pred_3.created_on = recent_date
    pred_3.save()

    # Recent + rated (should NOT be deleted)
    human_msg_4 = AssistantChatMessage.objects.create(
        chat=chat, role="human", content="Q4", created_on=recent_date
    )
    ai_msg_4 = AssistantChatMessage.objects.create(
        chat=chat, role="ai", content="A4", created_on=recent_date
    )
    pred_4 = AssistantChatPrediction.objects.create(
        human_message=human_msg_4,
        ai_response=ai_msg_4,
        prediction={},
        human_sentiment=AssistantChatPrediction.SENTIMENT_MAP["DISLIKE"],
    )
    pred_4.created_on = recent_date
    pred_4.save()

    handler = AssistantHandler()
    deleted_count, _ = handler.delete_predictions(
        older_than_days=30, exclude_rated=True
    )

    # Only old unrated should be deleted
    assert deleted_count == 1
    assert AssistantChatPrediction.objects.count() == 3

    # Verify the correct prediction was deleted
    assert not AssistantChatPrediction.objects.filter(id=pred_1.id).exists()
    assert AssistantChatPrediction.objects.filter(id=pred_2.id).exists()
    assert AssistantChatPrediction.objects.filter(id=pred_3.id).exists()
    assert AssistantChatPrediction.objects.filter(id=pred_4.id).exists()


@pytest.mark.django_db
def test_delete_predictions_custom_days_threshold(enterprise_data_fixture):
    """Test deletion with different day thresholds."""

    user = enterprise_data_fixture.create_user()
    workspace = enterprise_data_fixture.create_workspace(user=user)

    chat = AssistantChat.objects.create(user=user, workspace=workspace)

    # Create predictions at different ages
    very_old = datetime.now(timezone.utc) - timedelta(days=100)
    medium_old = datetime.now(timezone.utc) - timedelta(days=50)
    recent = datetime.now(timezone.utc) - timedelta(days=5)

    for age, label in [
        (very_old, "very_old"),
        (medium_old, "medium"),
        (recent, "recent"),
    ]:
        human_msg = AssistantChatMessage.objects.create(
            chat=chat, role="human", content=f"Q {label}", created_on=age
        )
        ai_msg = AssistantChatMessage.objects.create(
            chat=chat, role="ai", content=f"A {label}", created_on=age
        )
        pred = AssistantChatPrediction.objects.create(
            human_message=human_msg, ai_response=ai_msg, prediction={}
        )
        pred.created_on = age
        pred.save()

    handler = AssistantHandler()

    # Delete predictions older than 60 days (should delete 1)
    deleted_count, _ = handler.delete_predictions(older_than_days=60)
    assert deleted_count == 1
    assert AssistantChatPrediction.objects.count() == 2

    # Delete predictions older than 10 days (should delete 1 more)
    deleted_count, _ = handler.delete_predictions(older_than_days=10)
    assert deleted_count == 1
    assert AssistantChatPrediction.objects.count() == 1


@pytest.mark.django_db
def test_delete_predictions_empty_database():
    """Test that deletion returns 0 when no predictions exist."""

    handler = AssistantHandler()
    deleted_count, _ = handler.delete_predictions(older_than_days=30)

    assert deleted_count == 0


@pytest.mark.django_db
def test_delete_predictions_return_count_matches_deleted(enterprise_data_fixture):
    """Test that the return count matches the number of deleted predictions."""

    user = enterprise_data_fixture.create_user()
    workspace = enterprise_data_fixture.create_workspace(user=user)

    chat = AssistantChat.objects.create(user=user, workspace=workspace)
    old_date = datetime.now(timezone.utc) - timedelta(days=35)

    # Create exactly 5 old unrated predictions
    for i in range(5):
        human_msg = AssistantChatMessage.objects.create(
            chat=chat, role="human", content=f"Question {i}", created_on=old_date
        )
        ai_msg = AssistantChatMessage.objects.create(
            chat=chat, role="ai", content=f"Answer {i}", created_on=old_date
        )
        pred = AssistantChatPrediction.objects.create(
            human_message=human_msg, ai_response=ai_msg, prediction={}
        )
        pred.created_on = old_date
        pred.save()

    # Create 2 rated predictions that should NOT be deleted
    for i in range(2):
        human_msg = AssistantChatMessage.objects.create(
            chat=chat, role="human", content=f"Rated Q {i}", created_on=old_date
        )
        ai_msg = AssistantChatMessage.objects.create(
            chat=chat, role="ai", content=f"Rated A {i}", created_on=old_date
        )
        pred = AssistantChatPrediction.objects.create(
            human_message=human_msg,
            ai_response=ai_msg,
            prediction={},
            human_sentiment=AssistantChatPrediction.SENTIMENT_MAP["LIKE"],
        )
        pred.created_on = old_date
        pred.save()

    handler = AssistantHandler()
    deleted_count, _ = handler.delete_predictions(older_than_days=30)

    # Should delete exactly 5 unrated predictions
    assert deleted_count == 5
    # Should have 2 rated predictions remaining
    assert AssistantChatPrediction.objects.count() == 2
