"""Валідатори завантажуваних файлів: розширення, розмір і сигнатура (магічні байти)."""
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError

# перші байти файлів дозволених типів
SIGNATURES = {
    'pdf': (b'%PDF',),
    'docx': (b'PK\x03\x04',),
    'doc': (b'\xd0\xcf\x11\xe0',),
}


def validate_resume_file(upload):
    """Приймає лише PDF/DOC/DOCX розміром до RESUME_MAX_SIZE_MB, перевіряє заголовок файлу."""
    ext = Path(upload.name).suffix.lower().lstrip('.')
    allowed = settings.RESUME_ALLOWED_EXTENSIONS
    if ext not in allowed:
        raise ValidationError(f'Недопустимий тип файлу «.{ext}». Дозволено: {", ".join(allowed)}.')

    limit = settings.RESUME_MAX_SIZE_MB * 1024 * 1024
    if upload.size > limit:
        raise ValidationError(f'Файл завеликий: максимум {settings.RESUME_MAX_SIZE_MB} МБ.')

    head = upload.read(8)
    upload.seek(0)
    if not any(head.startswith(sig) for sig in SIGNATURES[ext]):
        raise ValidationError('Вміст файлу не відповідає його розширенню.')
