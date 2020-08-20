from adctest.helpers.base_config import BaseConfig


class Config(BaseConfig):
    """
    Конфиг для e2e-тестов. значения атрибутов и вложенных словарей могут быть следующих типов:
    [str, int, float, Decimal, bool]. При попытке установить любой другой тип будет вызвано исключение.
    ----------------
    Поддерживается обновление конфига из переменных окружения. Для этого необходимо, чтобы был определен
    атрибут UPDATE_FROM_ENV = True и в атрибуте ENV_KEY_PREFIX был прописан префикс для переменных
    окружения, которые необходимо использовать. Каждая такая переменная должна начинаться с этого префикса.
    Между вложенными атрибутами необходимо указывать `__`.
    """
    UPDATE_FROM_ENV = True
    ENV_KEY_PREFIX = 'test'

    # base configurations for applications
    BASE_APP_CONFIG = {
    }

    CRON_RELATIVE_PATH = ''
    CRON_TIMEOUT = 30

    WEB_DRIVER_WAIT = 10
    WEB_DRIVER_LOG_LEVEL = 'warning'
    SCREENSHOT_PATH = '/tmp/selenium_screenshots'
    ENABLE_CONSOLE_LOG = True
    CONSOLE_LOG_PATH = '/tmp/selenium_console_logs'

    # chrome driver configuration (https://chromedriver.chromium.org/)
    CHROME_DRIVER_URL = 'https://chromedriver.storage.googleapis.com/'
    CHROME_DRIVER_VER = 'LATEST_RELEASE'
    # Мажорная версия драйвера должна совпадать с мажорной версией хрома
    # Если падает ошибка с текстом: This version of ChromeDriver only supports Chrome version XXX
    # то надо сходить сюда https://chromedriver.chromium.org/downloads и взять подходящую версию
    DEFAULT_DRIVER_VER = '81.0.4044.69'
    # тип системы, для которой нужен драйвер (полный список по ссылке выше)
    CHROME_DRIVER_FILE_NAME = 'chromedriver_linux64.zip'
    # если пустая строка, то используется дефолтный в tmp
    CHROME_DRIVER_PATH = ''
    # нужно ли скачивать драйвер при каждом запуске тестов
    RELOAD_DRIVER = True
    # убивать драйвер после тестов (если выставить False, то браузер не будет закрыт)
    KILL_DRIVER = True
    # меняент дефолт selenium по ожиданию загрузки страницы
    DRIVER_PAGE_LOAD_TIMEOUT = 20

    # конфигурации для хрома
    # headless_mode (ставить true, если запуск необходим в среде без графической оболочки)
    CHROME_HEADLESS_MODE = False
    # опции для запуска хрома (разделитель параметров - ";")
    CHROME_OPTIONS = 'window-size=1920,1080;'
    CHROME_DOWNLOADS_PATH = '/tmp/chrome_downloads'

    DATA_E2E_ATTRIBUTE = 'data-e2e'
    TABLE_E2E_ATTRIBUTE = 'data-e2e-table'
    DEFAULT_TABLE_TAG = 'p-table'


config = Config()
