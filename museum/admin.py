from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from .models import Era, Topic, Card

admin.site.site_header = 'Карманный музей · мастерская'
admin.site.site_title = 'Карманный музей'
admin.site.index_title = 'Материалы и пользователи'

@admin.action(description='Опубликовать выбранные материалы')
def publish(modeladmin, request, queryset):
    for obj in queryset:
        obj.published = True
        try: obj.save()
        except ValidationError as exc: modeladmin.message_user(request, f'{obj}: {"; ".join(exc.messages)}', messages.ERROR)
        else: modeladmin.message_user(request, f'Опубликовано: {obj}', messages.SUCCESS)

@admin.action(description='Снять выбранные материалы с публикации')
def unpublish(modeladmin, request, queryset):
    for obj in queryset:
        obj.published = False
        try: obj.save()
        except ValidationError as exc: modeladmin.message_user(request, '; '.join(exc.messages), messages.ERROR)

class ContentAdmin(admin.ModelAdmin):
    actions = [publish, unpublish]
    list_filter = ['published']
    search_fields = ['title']
    def has_delete_permission(self, request, obj=None): return False

@admin.register(Era)
class EraAdmin(ContentAdmin):
    list_display = ['title', 'period', 'order', 'published']
    prepopulated_fields = {'slug': ('title',)}

@admin.register(Topic)
class TopicAdmin(ContentAdmin):
    list_display = ['title', 'era', 'published']
    list_filter = ['era', 'published']
    prepopulated_fields = {'slug': ('title',)}

@admin.register(Card)
class CardAdmin(ContentAdmin):
    list_display = ['title', 'topic', 'type', 'published']
    list_filter = ['topic__era', 'type', 'published']
