from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from PIL import Image, UnidentifiedImageError

def validate_image(value):
    if value.size > 5 * 1024 * 1024:
        raise ValidationError('Размер изображения не должен превышать 5 МБ.')
    was_closed = value.closed
    try:
        value.open('rb')
        img = Image.open(value)
        if img.format not in ('JPEG', 'PNG', 'WEBP'):
            raise ValidationError('Допустимы только JPEG, PNG и WebP.')
        img.verify()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise ValidationError('Файл не является допустимым изображением.')
    finally:
        if was_closed:
            value.close()
        else:
            value.seek(0)

class Era(models.Model):
    title = models.CharField('Название', max_length=160)
    slug = models.SlugField(unique=True)
    description = models.TextField('Описание')
    period = models.CharField('Период', max_length=100)
    order = models.PositiveIntegerField('Порядок', default=0)
    published = models.BooleanField('Опубликована', default=False)
    class Meta:
        ordering = ['order', 'pk']
        verbose_name = 'эпоха'
        verbose_name_plural = 'эпохи'
    def __str__(self): return self.title

class Topic(models.Model):
    era = models.ForeignKey(Era, on_delete=models.PROTECT, related_name='topics', verbose_name='Эпоха')
    title = models.CharField('Название', max_length=180)
    slug = models.SlugField()
    description = models.TextField('Описание')
    order = models.PositiveIntegerField('Порядок', default=0)
    published = models.BooleanField('Опубликована', default=False)
    class Meta:
        ordering = ['order', 'pk']
        constraints = [models.UniqueConstraint(fields=['era', 'slug'], name='unique_topic_slug_in_era')]
        verbose_name = 'тема'
        verbose_name_plural = 'темы'
    def __str__(self): return self.title
    def clean(self):
        if self.pk and self.quizzes.exclude(era_id=self.era_id).exists():
            raise ValidationError('Эпоха темы должна совпадать с эпохой её викторин.')
        if self.published:
            if not self.pk or sorted(self.cards.filter(published=True).values_list('type', flat=True)) != sorted(Card.Type.values):
                raise ValidationError('Для публикации нужны ровно четыре опубликованные карточки, по одной каждого типа.')
            quiz = self.quizzes.filter(published=True, kind='mini').first()
            if not quiz: raise ValidationError('Нужна опубликованная минивикторина.')
            quiz.validate_content()
    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

class Card(models.Model):
    class Type(models.TextChoices):
        EVENT = 'event', 'Событие'
        PERSON = 'person', 'Человек'
        OBJECT = 'object', 'Предмет'
        FACT = 'fact', 'Интересный факт'
    topic = models.ForeignKey(Topic, on_delete=models.PROTECT, related_name='cards', verbose_name='Тема')
    type = models.CharField('Тип', max_length=10, choices=Type.choices)
    title = models.CharField('Заголовок', max_length=200)
    teaser = models.TextField('Анонс')
    text = models.TextField('Основной текст')
    period = models.CharField('Дата или период', max_length=100)
    image = models.ImageField('Иллюстрация', upload_to='cards/', blank=True, validators=[validate_image])
    caption = models.CharField('Подпись', max_length=250, blank=True)
    alt = models.CharField('Альтернативный текст', max_length=250, blank=True)
    source = models.URLField('Источник')
    order = models.PositiveIntegerField('Порядок', default=0)
    published = models.BooleanField('Опубликована', default=False)
    class Meta:
        ordering = ['order', 'pk']
        verbose_name = 'карточка'
        verbose_name_plural = 'карточки'
    def __str__(self): return self.title
    def clean(self):
        if self.published and self.image and (not self.alt.strip() or not self.caption.strip()):
            raise ValidationError('У иллюстрации нужны подпись и альтернативный текст.')
        if self.topic_id and Topic.objects.filter(pk=self.topic_id, published=True).exists():
            previous = Card.objects.filter(pk=self.pk).first() if self.pk else None
            if not previous or previous.topic_id != self.topic_id or previous.type != self.type or not self.published:
                raise ValidationError('Сначала снимите тему с публикации, чтобы менять состав карточек.')
        if self.pk:
            previous = Card.objects.get(pk=self.pk)
            if previous.topic_id != self.topic_id and previous.topic.published:
                raise ValidationError('Сначала снимите прежнюю тему с публикации.')
    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)
    def delete(self, *args, **kwargs):
        if self.topic.published: raise ValidationError('Сначала снимите тему с публикации.')
        return super().delete(*args, **kwargs)

class CardProgress(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    card = models.ForeignKey(Card, on_delete=models.PROTECT)
    marked_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['user', 'card'], name='unique_read_card')]
