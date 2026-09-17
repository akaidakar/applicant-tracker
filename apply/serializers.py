from rest_framework import serializers

from .models import Application, Note, Stage, StageEntry, allowed_next_stages


class ApplicantSubmissionSerializer(serializers.Serializer):
    """The gist's field rules and messages, kept so a submitter's error handling still matches."""

    timestamp = serializers.DateTimeField(
        error_messages={
            "required": "timestamp is required",
            "invalid": "timestamp must be a valid ISO 8601 datetime (e.g., 2026-01-06T16:59:37.571Z)",
        },
    )
    name = serializers.CharField(
        error_messages={"required": "name is required", "blank": "name cannot be blank"},
    )
    email = serializers.EmailField(
        error_messages={
            "required": "email is required",
            "invalid": "email must be a valid email address",
            "blank": "email cannot be blank",
        },
    )
    resume_link = serializers.URLField(
        error_messages={
            "required": "resume_link is required",
            "invalid": "resume_link must be a valid URL",
            "blank": "resume_link cannot be blank",
        },
    )
    repository_link = serializers.URLField(
        error_messages={
            "required": "repository_link is required",
            "invalid": "repository_link must be a valid URL (e.g., https://github.com/user/repo)",
            "blank": "repository_link cannot be blank",
        },
    )
    action_run_link = serializers.URLField(
        error_messages={
            "required": "action_run_link is required",
            "invalid": "action_run_link must be a valid URL (e.g., https://github.com/user/repo/actions/runs/123)",
            "blank": "action_run_link cannot be blank",
        },
    )


class StageField(serializers.Field):
    """Renders a stage value as {"value", "label"} so clients never hardcode labels."""

    def __init__(self, **kwargs):
        kwargs["read_only"] = True
        super().__init__(**kwargs)

    def to_representation(self, value):
        return stage_json(value)


def stage_json(value):
    return {"value": value, "label": Stage(value).label}


class NoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Note
        fields = ["id", "content", "created_at"]


class StageEntrySerializer(serializers.ModelSerializer):
    stage = StageField()
    notes = NoteSerializer(many=True, read_only=True)

    class Meta:
        model = StageEntry
        fields = ["stage", "entered_at", "notes"]


class ApplicationListSerializer(serializers.ModelSerializer):
    stage = StageField()

    class Meta:
        model = Application
        fields = ["id", "name", "email", "submitted_at", "receipt", "stage"]


class ApplicationDetailSerializer(ApplicationListSerializer):
    allowed_next_stages = serializers.SerializerMethodField()
    history = StageEntrySerializer(source="stage_entries", many=True, read_only=True)

    class Meta(ApplicationListSerializer.Meta):
        fields = ApplicationListSerializer.Meta.fields + [
            "resume_link",
            "repository_link",
            "action_run_link",
            "allowed_next_stages",
            "history",
        ]

    def get_allowed_next_stages(self, application):
        return [stage_json(s) for s in allowed_next_stages(application.stage)]


class NoteCreateSerializer(serializers.Serializer):
    content = serializers.CharField()


class StageChangeSerializer(serializers.Serializer):
    stage = serializers.ChoiceField(choices=Stage.choices)
