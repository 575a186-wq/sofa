# Niche Research Pipeline — PRD

> Опорные материалы: `D:\picture_open\project-memory-ai-pod-etsy.md` (концепция),
> разделы 4.6 (воронка), 4.7 (скоринг), 5.2 (структура).
> Версия: 0.1 (черновик для реализации Фазы 1).

## 1. Цель

Скрипт, который раз в неделю (или вручную) генерирует топ кандидатов ниш для
POD-бизнеса:

1. Читает темы-кандидаты из `config/candidate_seeds.yaml`.
2. Для каждой темы запрашивает Google Trends (через `trendspyg`, нужен Chrome) —
   интерес за 12 месяцев, рост в %.
3. Для каждой темы запрашивает Etsy Open API v3 (`findAllListingsActive`) —
   количество активных листингов, среднюю цену, средний возраст топ-листингов.
4. Считает `opportunity_score` по формуле (п. 4.7 концепции).
5. Сохраняет топ-15 в `output/weekly_report.md` с обоснованием.

## 2. Входные данные

### `config/candidate_seeds.yaml`

Поля каждой темы:

| Поле | Тип | Обязательность | Описание |
|---|---|---|---|
| `id` | string | да | Уникальный slug темы |
| `name` | string | да | Человекочитаемое имя ниши |
| `keywords` | string[] | да | Поисковые ключи для Etsy / Trends |
| `art_type` | string | да | `parametric` (Тип B) или `generative` (Тип A) |
| `automation_fit` | float | да | 1.0 / 0.3–0.5 по концепции п. 4.7 |
| `source_data` | string | опц. | Что рендерится в арт (lat/long, аудио, GPX...) |
| `geo` | string | опц. | Регион для Trends/Etsy (по умолчанию `US`) |

## 3. Выходные данные

### `output/weekly_report.md`

Три секции:

1. **Заголовок**: дата, режим (`dry-run` / `live`), число оценённых ниш.
2. **Топ-15** — таблица: `rank | niche | final_score | opportunity_score |
   trend_growth% | etsy_listings | avg_price | avg_age_days | art_type`.
3. **Обоснование** — по каждому кандидату 1–2 строки: почему оценка такая
   (например, «рост Trends X%, листингов мало, средний возраст молодой»).

### `output/logs/pipeline-YYYYMMDD-HHMMSS.log`

Запись шагов, ошибок fetchers, предупреждений. Ротация не нужна (файл на дату).

## 4. Режимы

| Режим | Когда | Поведение |
|---|---|---|
| **dry-run** | `ETSY_API_KEY` отсутствует или `--dry-run` | Etsy-данные — детерминированные fake-значения (на основе `hash(keywords)` — стабильны между запусками); Trends — реальные если Chrome доступен, иначе пропуск с пометкой. Отчёт помечается `dry-run`. |
| **live** | `ETSY_API_KEY` задан и не `--dry-run` | Реальные запросы к Etsy. |

Trends в любом режиме реальный (бесплатный), но при недоступности Chrome —
грациозный пропуск, колонка `trend_growth% = n/a`, рост не наказывает скор.

## 5. Технические требования

- Python 3.11+ (локально 3.13), зависимости в `requirements.txt`.
- `ETSY_API_KEY` — среда (переменная окружения или `.env`),
  значение формата `keystring:shared_secret` (Etsy v3).
- Etsy: `GET /v3/application/listings/active`, заголовок `x-api-key: <value>`.
  Параметры: `keywords`, `limit=100`, пагинация offset до лимита выборки
  (по умолчанию 300 листингов на тему — консервативно к rate limit).
  Между запросами пауза 1–2 с. Retry: 429/5xx — до 4 попыток,
  экспоненциальная пауза 5→10→20→40 с (±jitter).
- Trends: `trendspyg.download_google_trends_interest_over_time`,
  timeframe `today 12-m`. Рост = (сред. последних 3 мес − сред. пред. 9 мес) /
  сред. пред. 9 мес × 100. Серия короче 6 точек → `None`.
- Скоринг — в `src/scoring/score_niches.py` (формула п. 4.7, веса в конфиге).
- Тесты: `pytest`, покрыть скоринг, dry-run Etsy, грациозный пропуск Trends.

## 6. Что НЕ делать

- Не публиковать ничего в Etsy автоматически на этом этапе.
- Не скрапить eRank/EverBee/Pinterest Trends / Google Trends HTML напрямую.
- Не хранить ключи в коде, только `.env` (в `.gitignore`) / GitHub Secrets.
- Не использовать агрессивный параллелизм к Etsy API.
- Не добавлять `social_signals.py` (TikTok/Reddit) в Фазе 1 — хук в скоринге с весом 0.

## 7. Статус и следующий шаг

- [ ] Реализовать `src/fetchers/etsy_client.py` (dry-run + live)
- [ ] Реализовать `src/fetchers/trends_client.py` (trendspyg + graceful)
- [ ] Реализовать `src/scoring/score_niches.py`
- [ ] Реализовать `src/pipeline.py` + `config/candidate_seeds.yaml`
- [ ] Тесты (`pytest`) зелёные
- [ ] Локальный dry-run прогон → `output/weekly_report.md`
- [ ] GitHub Actions `weekly-research.yml` (cron) — Фаза 2