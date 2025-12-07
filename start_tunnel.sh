#!/usr/bin/env bash
set -e

# Переходим в папку проекта (где лежит app.py, start_mirrors.sh и т.д.)
cd "$(dirname "$0")"

echo "🔍 Проверяю FastAPI на http://127.0.0.1:8011/health ..."

# Быстрая проверка, жив ли API
if curl -s "http://127.0.0.1:8011/health" | grep -q "ok"; then
  echo "✅ FastAPI отвечает, можно стартовать туннель."
else
  echo "⚠️ FastAPI не отвечает на 8011."
  echo "   Сначала запусти сервер:  ./start_mirrors.sh"
  exit 1
fi

echo "🧹 Убиваю старые процессы cloudflared (если есть)..."
killall cloudflared 2>/dev/null || true

echo "🚀 Запускаю новый Cloudflare Tunnel к http://127.0.0.1:8011 ..."
echo "   Ожидай строку с URL вида https://***.trycloudflare.com"

# Запускаем cloudflared и одновременно парсим строку с туннелем
cloudflared tunnel --url http://127.0.0.1:8011 2>&1 | awk '
/trycloudflare.com/ {
  # В этой строке Cloudflare пишет адрес туннеля
  url=$NF
  print ""
  print "🌐 Tunnel URL: " url
  print "👉 Этот адрес нужно вставить в n8n (например:"
  print "   " url "/collect_mirrors_interactive )"
  print ""
}
{ print }'

