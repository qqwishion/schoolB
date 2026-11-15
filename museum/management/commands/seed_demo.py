from pathlib import Path
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from museum.models import Era, Topic, Card
from museum.demo_data import ERAS, TOPICS, FINALS
from quizzes.models import Quiz, Question, Choice

class Command(BaseCommand):
    help = 'Загружает 3 эпохи, 9 тем, 36 карточек и 24 вопроса без дублей и изменения существующих материалов.'

    @transaction.atomic
    def handle(self, *args, **options):
        eras = []
        for order, (slug, title, period, description) in enumerate(ERAS):
            era, created = Era.objects.get_or_create(slug=slug, defaults=dict(title=title, period=period, description=description, order=order))
            eras.append((era, created))
        for number, data in enumerate(TOPICS):
            era = eras[data['era']][0]
            topic, created = Topic.objects.get_or_create(era=era, slug=data['slug'], defaults=dict(title=data['title'], description=data['description'], order=number % 3))
            if not created:
                # Existing content and publication decisions belong to the administrator.
                continue
            for order, ((kind, _), (title, period, teaser, text)) in enumerate(zip(Card.Type.choices, data['cards'])):
                asset = Path(settings.BASE_DIR) / 'demo_assets' / f'{data["slug"]}-{kind}.png'
                if not asset.exists(): raise CommandError(f'Отсутствует иллюстрация: {asset}')
                card = Card(topic=topic, type=kind, title=title, period=period, teaser=teaser, text=text, order=order, source=data['source'], published=True, caption=f'Авторская учебная схема: {title}. Не является изображением подлинного экспоната.', alt=f'Учебная иллюстрация к карточке «{title}»')
                # Deterministic path also avoids duplicate files after a rolled-back seed.
                filename = f'demo/{asset.name}'
                if not settings.MEDIA_ROOT.joinpath(filename).exists():
                    from django.core.files.storage import default_storage
                    default_storage.save(filename, ContentFile(asset.read_bytes()))
                card.image = filename
                card.save()
            quiz = Quiz.objects.create(era=era, topic=topic, kind='mini', title=f'Проверь себя: {topic.title}')
            self.fill_quiz(quiz, [data['mini']], number)
            topic.published = True
            topic.save()
        for index, (era, created) in enumerate(eras):
            if not Quiz.objects.filter(era=era, kind='final').exists():
                quiz = Quiz.objects.create(era=era, kind='final', title=f'Итоги: {era.title}')
                self.fill_quiz(quiz, FINALS[index], index)
            # Do not republish an era deliberately hidden by the administrator.
            if created:
                era.published = True
                era.save()
        self.stdout.write(self.style.SUCCESS('Демонстрационный набор готов. Существующие материалы и результаты сохранены.'))

    def fill_quiz(self, quiz, items, offset):
        for order, (text, choices, explanation) in enumerate(items):
            question = Question.objects.create(quiz=quiz, text=text, explanation=explanation, order=order)
            # Rotate choices deterministically, so the correct answer is not always first.
            rotation = (order + offset + 1) % 4
            indexed = list(enumerate(choices))
            indexed = indexed[rotation:] + indexed[:rotation]
            for position, (original, label) in enumerate(indexed):
                Choice.objects.create(question=question, text=label, correct=original == 0, order=position)
        quiz.published = True
        quiz.save()
