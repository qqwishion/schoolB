from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from .models import Era, Topic, Card, CardProgress
from quizzes.services import visible_quizzes, best_results, total_score
from quizzes.models import QuizAttempt

def visible_cards():
    return Card.objects.filter(published=True, topic__published=True, topic__era__published=True).select_related('topic__era')

def era_rows(user):
    rows = []
    for era in Era.objects.filter(published=True):
        cards = visible_cards().filter(topic__era=era)
        total = cards.count()
        marked = CardProgress.objects.filter(user=user, card__in=cards).count() if user.is_authenticated else 0
        best = None
        if user.is_authenticated:
            results = best_results(user).filter(quiz__era=era, quiz__kind='final')
            best = max((x['correct'] for x in results), default=None)
        rows.append({'era': era, 'total': total, 'marked': marked, 'percent': round(marked / total * 100) if total else 0, 'best': best, 'topics': era.topics.filter(published=True), 'quiz': visible_quizzes().filter(era=era, kind='final').first()})
    return rows

def home(request):
    return render(request, 'museum/home.html', {'rows': era_rows(request.user), 'card_count': visible_cards().count(), 'topic_count': Topic.objects.filter(published=True, era__published=True).count()})

def eras(request): return render(request, 'museum/eras.html', {'rows': era_rows(request.user)})

def sources(request):
    from .demo_data import TOPICS
    return render(request, 'museum/sources.html', {'topics': TOPICS})

def era_detail(request, slug):
    era = get_object_or_404(Era, slug=slug, published=True)
    row = next(r for r in era_rows(request.user) if r['era'].pk == era.pk)
    return render(request, 'museum/era.html', {'row': row})

def catalog(request):
    cards = visible_cards()
    era = request.GET.get('era', '')
    kind = request.GET.get('type', '')
    query = request.GET.get('q', '').strip()
    if era: cards = cards.filter(topic__era__slug=era)
    if kind: cards = cards.filter(type=kind)
    if query: cards = cards.filter(Q(title__icontains=query) | Q(text__icontains=query) | Q(teaser__icontains=query))
    # SQLite's default LIKE is ASCII-only. Casefold the search in local mode too.
    from django.db import connection
    if query and connection.vendor == 'sqlite':
        base = visible_cards()
        if era: base = base.filter(topic__era__slug=era)
        if kind: base = base.filter(type=kind)
        ids = [c.pk for c in base if query.casefold() in f'{c.title} {c.teaser} {c.text}'.casefold()]
        cards = visible_cards().filter(pk__in=ids)
    return render(request, 'museum/catalog.html', {'cards': cards, 'eras': Era.objects.filter(published=True), 'types': Card.Type.choices, 'selected_era': era, 'selected_type': kind, 'q': query})

def topic_detail(request, pk):
    topic = get_object_or_404(Topic, pk=pk, published=True, era__published=True)
    cards = visible_cards().filter(topic=topic)
    marked = set(CardProgress.objects.filter(user=request.user, card__in=cards).values_list('card_id', flat=True)) if request.user.is_authenticated else set()
    return render(request, 'museum/topic.html', {'topic': topic, 'cards': cards, 'marked_ids': marked, 'quiz': visible_quizzes().filter(topic=topic).first()})

def card_detail(request, pk):
    card = get_object_or_404(visible_cards(), pk=pk)
    siblings = list(visible_cards().filter(topic=card.topic))
    index = siblings.index(card)
    marked = request.user.is_authenticated and CardProgress.objects.filter(user=request.user, card=card).exists()
    return render(request, 'museum/card.html', {'card': card, 'marked': marked, 'previous': siblings[index-1] if index else None, 'following': siblings[index+1] if index+1 < len(siblings) else None})

@login_required
@require_POST
def mark_card(request, pk):
    card = get_object_or_404(visible_cards(), pk=pk)
    if request.POST.get('action') == 'mark': CardProgress.objects.get_or_create(user=request.user, card=card)
    elif request.POST.get('action') == 'unmark': CardProgress.objects.filter(user=request.user, card=card).delete()
    return redirect('card', pk=pk)

@login_required
def profile(request):
    return render(request, 'museum/profile.html', {'rows': era_rows(request.user), 'score': total_score(request.user), 'bests': best_results(request.user), 'history': QuizAttempt.objects.filter(user=request.user, status='completed').select_related('quiz'), 'read_cards': visible_cards().filter(cardprogress__user=request.user)})
