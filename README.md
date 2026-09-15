# Niche Research Pipeline

Еженедельный исследовательский пайплайн для выбора ниш POD-бизнеса
(Etsy/Amazon). Ядро методологии описано в
[PROJECT MEMORY](../project-memory-ai-pod-etsy.md): воронка 4.6, скоринг 4.7,
подход «Тип B» (параметрический арт) 4.3.

## Что делает

Раз в неделю (cron / ручной запуск):

1. Берёт темы кандидатов из `config/candidate_seeds.yaml`
2. Для каждой темы запрашивает Google Trends (trendspyg + Chrome) — рост за 12 мес.
3. Для каждой темы запрашивает Etsy Open API v3 (`findAllListingsActive`) —
   количество активных листингов, средние цены, возраст топ-листингов
4. Считает `opportunity_score` × `automation_fit_score`
5. Пишет топ-15 в `output/weekly_report.md`

## Запуск

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt

# Dry-run (без Etsy API key — синтетические данные)
python src/pipeline.py

# Реальный прогон
set ETSY_API_KEY=keystring:shared_secret
python src/pipeline.py
```

## Фазы проекта

| Фаза | Статус |
|---|---|
| 0. Инфраструктура (git, конфиги) | в работе |
| 1. Код пайплайна исследования ниш | не начата |
| 2. Расписание в GitHub Actions | не начата |
| 3. Прогон воронки + ручной отбор ниш | не начата |
| 4. Генерация арта / публикация | вне скоупа |

## Правила (ToS)

- Не скрапить eRank/EverBee/Pinterest Trends — только ручная проверка.
- Не публиковать листинги автоматически на этом этапе.
- Ключи — только через переменные окружения.