from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from .models import QuizAttempt
from .services import visible_quizzes, submit_attempt
from museum.models import Era

def catalog(request):
    quizzes = visible_quizzes().select_related('era', 'topic')
    slug = request.GET.get('era', '')
    if slug: quizzes = quizzes.filter(era__slug=slug)
    return render(request, 'quizzes/catalog.html', {'quizzes': quizzes, 'eras': Era.objects.filter(published=True), 'selected_era': slug})

@login_required
def quiz_detail(request, pk):
    quiz = get_object_or_404(visible_quizzes(), pk=pk)
    if request.method == 'POST':
        attempt = QuizAttempt.objects.create(user=request.user, quiz=quiz)
        return redirect('attempt', pk=attempt.pk)
    return render(request, 'quizzes/start.html', {'quiz': quiz, 'count': quiz.questions.count(), 'maximum': 5 if quiz.kind == 'mini' else 50})

def attempt_context(attempt, data=None, error=None):
    if attempt.status == 'completed':
        answers = attempt.answers.select_related('question', 'choice').order_by('question__order', 'question__pk')
        review = [{'question': a.question.text, 'chosen': a.choice.text, 'correct': a.choice.correct, 'answer': a.question.choices.get(correct=True).text, 'explanation': a.question.explanation} for a in answers]
        return {'attempt': attempt, 'review': review, 'percent': round(attempt.correct_count / len(review) * 100) if review else 0, 'count': len(review)}
    # Explicitly construct the public payload: no answer flags or explanations before submission.
    questions = [{'id': q.pk, 'text': q.text, 'choices': [{'id': c.pk, 'text': c.text, 'selected': str(c.pk) == str((data or {}).get(f'question_{q.pk}'))} for c in q.choices.all()]} for q in attempt.quiz.questions.prefetch_related('choices')]
    return {'attempt': attempt, 'questions': questions, 'error': error}

@login_required
def attempt_detail(request, pk):
    attempt = get_object_or_404(QuizAttempt.objects.select_related('quiz'), pk=pk, user=request.user)
    if attempt.status != 'completed': get_object_or_404(visible_quizzes(), pk=attempt.quiz_id)
    return render(request, 'quizzes/attempt.html', attempt_context(attempt))

@login_required
@require_POST
def submit(request, pk):
    attempt = get_object_or_404(QuizAttempt.objects.select_related('quiz'), pk=pk, user=request.user)
    try: submit_attempt(pk, request.user, request.POST)
    except ValidationError as exc:
        return render(request, 'quizzes/attempt.html', attempt_context(attempt, request.POST, ' '.join(exc.messages)), status=400)
    return redirect('attempt', pk=pk)
