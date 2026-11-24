# Stockify

Stockify — учебный проект системы управления складом на Django, Jinja2 и PostgreSQL.
Цель проекта — показать надёжную обработку складских движений, а не только CRUD-операции.

## План разработки

1. Основа проекта и запуск через Docker Compose.
2. Каталог товаров, категорий и поставщиков.
3. Поступления, списания и история движений с контролем остатков.
4. Интерфейс управления на Bootstrap 5.
5. Отчёты, роли пользователей и документация.

## Запуск

Требуется Python 3.12+ и Docker Compose. Скопируйте `.env.example` в `.env`, задайте секретный ключ и пароль PostgreSQL, затем запустите базу (порт хоста — `5433`):

```bash
docker compose up -d db
```

Для работы Django локально создайте окружение, установите зависимости, примените миграции и запустите сервер:

```bash
python3.13 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python manage.py migrate
.venv/bin/python manage.py createsuperuser
.venv/bin/python manage.py runserver
```

Локальный сервер будет доступен на <http://localhost:8000/>; административная панель — на <http://localhost:8000/admin/>. Чтобы запустить весь проект в контейнерах, сначала примените миграции и создайте администратора, затем поднимите web и PostgreSQL:

```bash
docker compose run --rm web python manage.py migrate
docker compose run --rm web python manage.py createsuperuser
docker compose up --build
```

## Архитектурные принципы

- Изменения остатков оформляются отдельными складскими движениями.
- Списание запрещено, если доступного остатка недостаточно.
- Django отвечает за бизнес-логику и доступ к данным; Jinja2 — за пользовательские страницы.
- PostgreSQL — основное хранилище приложения.
