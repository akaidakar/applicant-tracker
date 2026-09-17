from rest_framework import serializers


class ApplicantSubmissionSerializer(serializers.Serializer):
    timestamp = serializers.DateTimeField()
    name = serializers.CharField()
    email = serializers.EmailField()
    resume_link = serializers.URLField()
    repository_link = serializers.URLField()
    action_run_link = serializers.URLField()
