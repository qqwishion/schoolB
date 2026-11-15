from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Max
from django.utils import timezone
from .models import Quiz, QuizAttempt, AttemptAnswer

def visible_quizzes():
    from django.db.models import Q
    return Quiz.objects.filter(published=True, era__published=True).filter(Q(kind='final') | Q(topic__published=True))

def best_results(user):
    return QuizAttempt.objects.filter(user=user, status='completed', quiz__in=visible_quizzes()).order_by().values('quiz_id', 'quiz__title', 'quiz__kind').annotate(best=Max('points'), correct=Max('correct_count'))

def total_score(user): return sum(row['best'] for row in best_results(user))

@transaction.atomic
def submit_attempt(attempt_id, user, data):
    attempt = QuizAttempt.objects.select_for_update().select_related('quiz').get(pk=attempt_id, user=user)
    if attempt.status == 'completed': return attempt
    if not visible_quizzes().filter(pk=attempt.quiz_id).exists(): raise ValidationError('Тест снят с публикации.')
    answers = []
    correct = 0
    for question in attempt.quiz.questions.prefetch_related('choices'):
        value = data.get(f'question_{question.pk}')
        choice = next((c for c in question.choices.all() if str(c.pk) == str(value)), None)
        if choice is None: raise ValidationError('Ответьте на каждый вопрос. Выберите вариант, относящийся к этому вопросу.')
        answers.append(AttemptAnswer(attempt=attempt, question=question, choice=choice))
        correct += int(choice.correct)
    for answer in answers: answer.save()
    attempt.correct_count = correct
    attempt.points = correct * (5 if attempt.quiz.kind == 'mini' else 10)
    attempt.finished_at = timezone.now()
    attempt.status = 'completed'
    attempt.save(update_fields=['correct_count', 'points', 'finished_at', 'status'])
    return attempt
