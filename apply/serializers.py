from rest_framework import serializers

from .models import Application, Note, Stage, StageEntry, allowed_next_stages


class ApplicantSubmissionSerializer(serializers.Serializer):
    timestamp = serializers.DateTimeField()
    name = serializers.CharField()
    email = serializers.EmailField()
    resume_link = serializers.URLField()
    repository_link = serializers.URLField()
    action_run_link = serializers.URLField()


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
