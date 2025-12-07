#!/usr/bin/env bash
set -e

# Переходим в папку проекта
cd "$(dirname "$0")"

# Активируем виртуальное окружение
source .venv/bin/activate

# Подгружаем переменные из .env (включая SERPER_API_KEY)
if [ -f ".env" ]; then
  set -a
  source .env
  set +a
fi

# Запускаем uvicorn
uvicorn app:app --reload --port 8011
