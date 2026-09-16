# RECOVERY — как поднять проект с нуля (за ~10 минут)

Сценарий: потерян ПК / папка `D:\picture_open\`, либо разработка продолжается другим инструментом.

## Что откуда берём

| Компонент | Источник |
|---|---|
| Код, конфиг ниш, CI, документация | GitHub `https://github.com/575a186-wq/sofa` |
| Ключ Etsy API | из личного бэкапа (zip `*.zip`) или с developer.etsy.com |
| Секрет CI `SOFA_PICTURE` | GitHub → Settings → Secrets (не восстановить из репо) |
| Окружение Python | создаётся заново из `requirements.txt` |
| Google Chrome | ставится отдельно |

## Шаги

### 1. Предустановки
- **Python 3.13+** (python.org, галочка «Add to PATH»)
- **Git** (git-scm.com)
- **Google Chrome** — обязателен для Google Trends (trendspyg)
- (опционально) **GitHub CLI** `gh` для работы с Actions из консоли

### 2. Клонируем код
```bash
git clone https://github.com/575a186-wq/sofa.git
cd sofa
```

### 3. Поднимаем окружение и проверяем
```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pytest            # ожидаем: 20 passed
```

### 4. Подключаем ключ Etsy
- Если есть личный бэкап-архив: распаковать `.env` рядом (файл `niche-research-pipeline\.env`, формат см. в `.env.example`).
- Если нет: `copy .env.example .env`, вписать ключ `ETSY_API_KEY=keystring:shared_secret` (developer.etsy.com → Your Apps).

### 5. Запуск
```bash
python src\pipeline.py              # при отсутствии ключа — dry-run (синтетика)
python src\pipeline.py --dry-run    # принудительно dry-run
# live: ключ из .env подхватится сам (python-dotenv)
```
Результат — `output\weekly_report.md` (рейтинг ниш).

### 6. GitHub Actions (авто-прогон раз в неделю)
- Workflow уже в репо (`.github\workflows\weekly-research.yml`, cron `0 8 * * 1`).
- Проверить, что секрет существует: `gh secret list` → должно быть `SOFA_PICTURE`.
- Ручной запуск: `gh workflow run "Weekly Niche Research"` или GitHub → Actions → Run workflow.
- Отчёты появляются в артефакте `weekly-report` (Actions → Summary).

## Частые нюансы

- **Google Trends 429**: Google блокирует и домашние, и облачные IP. Это НЕ поломка:
  пайплайн помечает тренд как `n/a`, в скоринге это нейтрально 50. Тренд — запасной
  сигнал; базовый сигнал (конкуренция Etsy) работает всегда.
- **`.env` нельзя коммитить** — он в `.gitignore`. Секрет CI хранится отдельно
  (GitHub Secrets, имя `SOFA_PICTURE`).
- **Путь к git на этом ПК без PATH**: `C:\Program Files\Git\bin\git.exe`.
- **gh без пути**: `C:\Program Files\GitHub CLI\bin\gh.exe`.

## Что НЕ нужно восстанавливать
`.venv\`, `__pycache__\`, `.pytest_cache\`, `output\logs\` — всё это генерируется заново.