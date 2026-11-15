from django.contrib import admin, messages
from django.db import transaction
from .models import Quiz, Question, Choice, QuizAttempt, AttemptAnswer
from museum.admin import ContentAdmin

@admin.action(description='Создать новую версию в черновике')
def clone(modeladmin, request, queryset):
    for quiz in queryset:
        with transaction.atomic():
            version = (Quiz.objects.filter(era=quiz.era, topic=quiz.topic, kind=quiz.kind).order_by('-version').values_list('version', flat=True).first() or 0) + 1
            copy = Quiz.objects.create(era=quiz.era, topic=quiz.topic, kind=quiz.kind, title=quiz.title, version=version)
            for question in quiz.questions.all():
                new = Question.objects.create(quiz=copy, text=question.text, explanation=question.explanation, order=question.order)
                for choice in question.choices.all(): Choice.objects.create(question=new, text=choice.text, correct=choice.correct, order=choice.order)
        modeladmin.message_user(request, f'Создан черновик: {copy}', messages.SUCCESS)

@admin.register(Quiz)
class QuizAdmin(ContentAdmin):
    list_display = ['title', 'era', 'kind', 'version', 'published']
    readonly_fields = ['published']
    actions = ContentAdmin.actions + [clone]
    def get_readonly_fields(self, request, obj=None):
        if obj and obj.frozen: return [f.name for f in self.model._meta.fields]
        return self.readonly_fields

class ChoiceInline(admin.TabularInline):
    model = Choice
    extra = 4
    max_num = 4

@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ['text', 'quiz', 'order']
    list_filter = ['quiz']
    search_fields = ['text']
    inlines = [ChoiceInline]
    def has_change_permission(self, request, obj=None):
        return super().has_change_permission(request, obj) and (not obj or not (obj.quiz.frozen or obj.quiz.published))
    def has_delete_permission(self, request, obj=None): return False
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'quiz': kwargs['queryset'] = Quiz.objects.filter(published=False, attempts__isnull=True)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

class HistoryAdmin(admin.ModelAdmin):
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False

@admin.register(QuizAttempt)
class AttemptAdmin(HistoryAdmin):
    list_display = ['user', 'quiz', 'status', 'correct_count', 'points', 'finished_at']
    list_filter = ['status', 'quiz']
    search_fields = ['user__username']

admin.site.register(AttemptAnswer, HistoryAdmin)
