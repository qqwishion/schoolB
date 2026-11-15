from django.shortcuts import render
def not_found(request, exception): return render(request, 'error.html', {'code': 404, 'message': 'Материал не найден или пока не опубликован.'}, status=404)
def forbidden(request, exception): return render(request, 'error.html', {'code': 403, 'message': 'Нет доступа. Обновите страницу и войдите в свою учётную запись.'}, status=403)
