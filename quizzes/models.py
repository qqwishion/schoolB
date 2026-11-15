from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

class Quiz(models.Model):
    era = models.ForeignKey('museum.Era', on_delete=models.PROTECT, related_name='quizzes', verbose_name='Эпоха')
    topic = models.ForeignKey('museum.Topic', on_delete=models.PROTECT, related_name='quizzes', null=True, blank=True, verbose_name='Тема')
    kind = models.CharField('Тип', max_length=5, choices=[('mini', 'Минивикторина'), ('final', 'Итоговый тест')])
    title = models.CharField('Название', max_length=200)
    version = models.PositiveIntegerField('Версия', default=1)
    published = models.BooleanField('Опубликован', default=False)
    class Meta:
        ordering = ['era__order', 'kind', 'pk']
        verbose_name = 'тест'
        verbose_name_plural = 'тесты'
        constraints = [
            models.CheckConstraint(condition=Q(kind='mini', topic__isnull=False) | Q(kind='final', topic__isnull=True), name='quiz_topic_kind'),
            models.UniqueConstraint(fields=['topic'], condition=Q(published=True, kind='mini'), name='one_live_mini'),
            models.UniqueConstraint(fields=['era'], condition=Q(published=True, kind='final'), name='one_live_final'),
        ]
    def __str__(self): return f'{self.title} · v{self.version}'
    @property
    def frozen(self): return bool(self.pk and self.attempts.exists())
    def validate_content(self):
        questions = list(self.questions.all()) if self.pk else []
        expected = 1 if self.kind == 'mini' else 5
        if len(questions) != expected: raise ValidationError(f'Для публикации требуется вопросов: {expected}.')
        for question in questions:
            if question.choices.count() != 4 or question.choices.filter(correct=True).count() != 1 or not question.explanation.strip():
                raise ValidationError(f'Вопрос «{question.text}»: нужны четыре ответа, ровно один правильный и пояснение.')
    def clean(self):
        if self.kind == 'mini' and not self.topic_id: raise ValidationError('Для минивикторины обязательна тема.')
        if self.kind == 'final' and self.topic_id: raise ValidationError('Итоговый тест относится только к эпохе.')
        if self.topic_id and self.topic.era_id != self.era_id: raise ValidationError('Тема и тест должны относиться к одной эпохе.')
        if self.frozen:
            old = Quiz.objects.get(pk=self.pk)
            if any(getattr(old, f) != getattr(self, f) for f in ['title', 'era_id', 'topic_id', 'kind', 'version']):
                raise ValidationError('У теста есть попытки. Создайте новую версию.')
        if self.published: self.validate_content()
        if self.pk and not self.published and self.topic_id and self.topic.published:
            raise ValidationError('Сначала снимите тему с публикации.')
    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

class Question(models.Model):
    quiz = models.ForeignKey(Quiz, on_delete=models.PROTECT, related_name='questions', verbose_name='Тест')
    text = models.TextField('Вопрос')
    explanation = models.TextField('Пояснение', blank=True)
    order = models.PositiveIntegerField('Порядок', default=0)
    class Meta:
        ordering = ['order', 'pk']
        verbose_name = 'вопрос'
        verbose_name_plural = 'вопросы'
    def __str__(self): return self.text
    def clean(self):
        if self.quiz_id and (self.quiz.frozen or self.quiz.published): raise ValidationError('Редактируйте вопросы только в черновике без попыток.')
        if self.pk:
            old = Question.objects.get(pk=self.pk)
            if old.quiz_id != self.quiz_id and (old.quiz.frozen or old.quiz.published): raise ValidationError('Нельзя переносить вопрос опубликованного теста или теста с попытками.')
    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)
    def delete(self, *args, **kwargs):
        self.clean()
        return super().delete(*args, **kwargs)

class Choice(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='choices', verbose_name='Вопрос')
    text = models.CharField('Ответ', max_length=300)
    correct = models.BooleanField('Правильный', default=False)
    order = models.PositiveIntegerField('Порядок', default=0)
    class Meta:
        ordering = ['order', 'pk']
        verbose_name = 'вариант ответа'
        verbose_name_plural = 'варианты ответа'
    def __str__(self): return self.text
    def clean(self):
        if self.question_id: self.question.clean()
        if self.pk:
            old = Choice.objects.get(pk=self.pk)
            if old.question_id != self.question_id: old.question.clean()
    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)
    def delete(self, *args, **kwargs):
        self.clean()
        return super().delete(*args, **kwargs)

class QuizAttempt(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='attempts')
    quiz = models.ForeignKey(Quiz, on_delete=models.PROTECT, related_name='attempts')
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=[('started', 'Начата'), ('completed', 'Завершена')], default='started')
    correct_count = models.PositiveIntegerField(default=0)
    points = models.PositiveIntegerField(default=0)
    class Meta:
        ordering = ['-started_at', '-pk']

class AttemptAnswer(models.Model):
    attempt = models.ForeignKey(QuizAttempt, on_delete=models.PROTECT, related_name='answers')
    question = models.ForeignKey(Question, on_delete=models.PROTECT)
    choice = models.ForeignKey(Choice, on_delete=models.PROTECT)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['attempt', 'question'], name='one_attempt_answer')]
    def clean(self):
        if self.choice.question_id != self.question_id or self.question.quiz_id != self.attempt.quiz_id:
            raise ValidationError('Ответ не относится к вопросу или тесту.')
    def save(self, *args, **kwargs):
        self.full_clean()
        if self.attempt.status == 'completed': raise ValidationError('Завершённую попытку менять нельзя.')
        return super().save(*args, **kwargs)
