from django.db import transaction
from django.utils import timezone
from jobs.models import Application, Candidate, CandidateSkill, Category, City, Interview, Skill, Vacancy, VacancySkill
from rest_framework import serializers


class CitySerializer(serializers.ModelSerializer):
    class Meta:
        model = City
        fields = ['id', 'name']


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name', 'slug']


class SkillSerializer(serializers.ModelSerializer):
    class Meta:
        model = Skill
        fields = ['id', 'name']


class SkillLevelSerializer(serializers.Serializer):
    """Навичка з рівнем: {"skill": "Python", "level": 4} — навичка вказується назвою."""
    skill = serializers.SlugRelatedField(slug_field='name', queryset=Skill.objects.all())
    level = serializers.IntegerField(min_value=1, max_value=5)


class VacancySerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source='company.name', read_only=True)
    skills = SkillLevelSerializer(source='vacancy_skills', many=True, required=False)

    class Meta:
        model = Vacancy
        fields = ['id', 'title', 'description', 'company', 'company_name', 'city', 'category', 'salary_min',
                  'salary_max', 'work_format', 'status', 'closes_at', 'skills', 'created']
        read_only_fields = ['id', 'company', 'created']

    def validate(self, attrs):
        low = attrs.get('salary_min', getattr(self.instance, 'salary_min', None))
        high = attrs.get('salary_max', getattr(self.instance, 'salary_max', None))
        if low is not None and high is not None and low > high:
            raise serializers.ValidationError({'salary_max': 'Максимальна зарплата менша за мінімальну.'})
        closes_at = attrs.get('closes_at')
        if closes_at and closes_at < timezone.localdate():
            raise serializers.ValidationError({'closes_at': 'Дата не може бути в минулому.'})
        return attrs

    def _save_skills(self, vacancy, items):
        """Замінює вимоги до навичок. Збереження Vacancy вже запланувало синхронізацію on_commit —
        вона виконається після коміту, коли навички вже записано."""
        if items is None:
            return
        vacancy.vacancy_skills.all().delete()
        VacancySkill.objects.bulk_create(
            [VacancySkill(vacancy=vacancy, skill=i['skill'], level=i['level']) for i in items])

    @transaction.atomic
    def create(self, validated_data):
        skills = validated_data.pop('vacancy_skills', None)
        vacancy = Vacancy.objects.create(**validated_data)
        self._save_skills(vacancy, skills)
        return vacancy

    @transaction.atomic
    def update(self, instance, validated_data):
        skills = validated_data.pop('vacancy_skills', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        self._save_skills(instance, skills)
        return instance


class CandidateSerializer(serializers.ModelSerializer):
    skills = SkillLevelSerializer(source='candidate_skills', many=True, required=False)

    class Meta:
        model = Candidate
        fields = ['id', 'full_name', 'headline', 'phone', 'city', 'expected_salary', 'skills']
        read_only_fields = ['id']

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get('request')
        # телефон бачить лише власник профілю й адміністратор
        if not request or not (request.user.is_staff or request.user.pk == instance.user_id):
            data.pop('phone', None)
        return data

    @transaction.atomic
    def update(self, instance, validated_data):
        skills = validated_data.pop('candidate_skills', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if skills is not None:
            instance.candidate_skills.all().delete()
            for item in skills:   # create() поштучно — щоб спрацювали сигнали інтеграції
                CandidateSkill.objects.create(candidate=instance, skill=item['skill'], level=item['level'])
        return instance


class ApplicationSerializer(serializers.ModelSerializer):
    vacancy_title = serializers.CharField(source='vacancy.title', read_only=True)
    candidate_name = serializers.CharField(source='candidate.full_name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Application
        fields = ['id', 'vacancy', 'vacancy_title', 'candidate', 'candidate_name', 'resume', 'cover_letter',
                  'status', 'status_display', 'created']
        read_only_fields = ['id', 'candidate', 'status', 'created']

    def validate_vacancy(self, vacancy):
        if not vacancy.accepts_applications():
            raise serializers.ValidationError('Вакансія закрита й не приймає заявок.')
        return vacancy

    def validate(self, attrs):
        request = self.context['request']
        candidate = request.user.candidate
        vacancy = attrs.get('vacancy')
        if vacancy and Application.objects.filter(candidate=candidate, vacancy=vacancy).exists():
            raise serializers.ValidationError({'vacancy': 'Ви вже подали заявку на цю вакансію.'})
        resume = attrs.get('resume')
        if resume and resume.candidate_id != candidate.pk:
            raise serializers.ValidationError({'resume': 'Можна вказати лише власне резюме.'})
        return attrs


class ApplicationStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Application.Status.choices)


class InterviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = Interview
        fields = ['id', 'application', 'scheduled_at', 'location', 'notes', 'created']
        read_only_fields = ['id', 'created']

    def validate_scheduled_at(self, value):
        if value < timezone.now():
            raise serializers.ValidationError('Співбесіду не можна призначити в минулому.')
        return value

    def validate_application(self, application):
        user = self.context['request'].user
        if application.vacancy.company.user_id != user.pk and not user.is_staff:
            raise serializers.ValidationError('Це не заявка на вашу вакансію.')
        return application
