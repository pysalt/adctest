from abc import ABCMeta
from typing import List, Dict, Optional
from urllib.parse import urljoin
from dataclasses import dataclass

from adctest.config import config
from adctest.page_helpers.scripts import PAGE_READY_SCRIPT, check_js_condition_is_true
from adctest.helpers.exceptions import BasePageException, PageNotOpened
from adctest.helpers.utils import get_parents_classes_attrs, get_base_url, add_url_params, get_id_from_url, \
    split_url_and_params
from adctest.pages.base_abstract import AbstractBasePage
from adctest.pages.base_navigation import BaseNavigation
from adctest.pages.uicomponents import Toast, ConfirmDialog
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC


@dataclass
class PageConfig:
    base_url: str
    page_loader_css_class: str
    """
    css-класс для поиска лоадера (ракета) страницы в верстке
    Устанавливается мета-классом из конфига, если не переопределен в классе наследнике
    """
    table_loader_css_class: str
    """
    css-класс для поиска лоадера таблицы в верстке
    Устанавливается мета-классом из конфига, если не переопределен в классе наследнике
    """
    modal_visible_css_class: str
    """
    css-класс для поиска открытого попапа на странице
    Устанавливается мета-классом из конфига, если не переопределен в классе наследнике
    """
    has_page_ready_script: bool = False
    """нужно ли проверять e2eReady атрибут после загрузки страницы селениумом, кстанавливается мета-классом"""


class BasePageMeta(ABCMeta):
    """
    базовый метакласс, который реализует основную логику создания классов страниц из сырых классов
    """

    def __new__(mcs, class_name, bases, attrs):
        """
        Args:
            class_name (str): the name of the class being created
            bases (list of class): the parents of the class being created
            attrs (str => obj dict): the attributes as defined in the class
                definition

        Returns:
            A new class
        """
        new_attrs = {}
        all_attrs = get_parents_classes_attrs(bases)
        all_attrs.update(attrs)

        page_conf: Optional[PageConfig] = all_attrs.get('page_conf')
        if not page_conf or not isinstance(page_conf, PageConfig):
            raise BasePageException('Page object must have "page_conf" attribute which inherit from PageConfig')

        new_attrs['_base_url'] = page_conf.base_url

        page_url = all_attrs.pop('page_url', None)
        if page_url is None:
            raise BasePageException(f'Page object must have "page_url" attribute')
        new_attrs['page_url'] = urljoin(page_conf.base_url, page_url)

        valid_urls = all_attrs.pop('valid_urls', [])
        valid_urls.append(page_url)
        new_attrs['valid_urls'] = [urljoin(page_conf.base_url, url) for url in valid_urls]

        all_attrs.update(new_attrs)

        new_class = type.__new__(mcs, class_name, bases, all_attrs)

        return new_class


class BasePage(AbstractBasePage):
    page_url: str = None
    """относительный роут страницы, устанавливается в сабклассе парсером"""
    page_conf: PageConfig
    """основные настройки страницы"""
    valid_urls: List[str] = []
    """относительные роуты, которые тоже могут вести на эту страницу (например, у логина здесь может быть logout)"""
    _base_url: str = None

    def __init__(self, fresh_session: bool = False, open_page: bool = True, query_params: Optional[Dict] = None,
                 **kwargs):
        """

        :param fresh_session: нужно ли очищать текущую сессию браузера (удалить куки и прочее)
        :param open_page: Если передать False, то будет создан объект без открытия страницы в браузере
        :param query_params: Можно передать словарь, который будет дописан к url, как query-строка
        :param kwargs:
        """
        super().__init__(fresh_session=fresh_session)
        if open_page:
            self.open(params=query_params)

        self._init_navigation_components()

    def _init_navigation_components(self):
        """
        инициализирует навигационные компоненты, если они есть
        :return:
        """
        for name, value in self.__class__.__dict__.items():
            if isinstance(value, BaseNavigation):
                value._init_from_page(self)

    def open(self, custom_url: Optional[str] = None, params: Optional[Dict] = None):
        """
        По умолчанию открывает page_url страницы.
        Если передать custom_url, то будет искать ссылку в valid_urls
        Если передать params, то допишет их к запросу
        Оба этих доп. параметры использовать только для ускорения работа (например, чтобы открыть вкладку
        статы с предустановленными фильтрами)
        :param custom_url: путь, относительно домена (должен быть указан в valid_urls страницы)
        :param params: параметры запроса
        :return:
        """
        url = self._make_valid_url(custom_url, params)
        self._open(url=url)
        self.wait_loaders_hidden()

    def _search_in_valid_urls(self, pattern: str) -> str:
        base_url, params = split_url_and_params(pattern)
        for url in self.valid_urls:
            if base_url.rstrip('/') in url:
                return f'{url}?{params}' if params else url
        raise PageNotOpened(f'You want to open url by pattern="{pattern}" '
                            f'but url not found in valid_urls: {self.valid_urls}')

    def _make_valid_url(self, custom_url: Optional[str] = None, params: Optional[Dict] = None) -> str:
        """
        Возвращает запрошенную ссылку, если она присутствует в valid_urls
        :param custom_url:
        :param params:
        :return:
        """
        url = self.page_url
        if custom_url:
            url = self._search_in_valid_urls(custom_url)
        if params:
            url = add_url_params(url, params)
        return url

    def check_opened(self):
        opened_url = get_base_url(self.opened_url)
        for url in self.valid_urls:
            if url.rstrip('/') in opened_url:
                return
        raise PageNotOpened(f'Get attr of {type(self).__name__}, but current url: {self.opened_url}')

    def wait_page_loaded(self) -> None:
        try:
            if self.page_conf.has_page_ready_script:
                self.wait.until(check_js_condition_is_true(PAGE_READY_SCRIPT))
        except TimeoutException:
            raise BasePageException('Check that "e2eReady" attribute set by frontend on the current page.')

    def wait_loader_not_visible(self) -> None:
        if self.page_conf.page_loader_css_class:
            self.wait.until(EC.invisibility_of_element_located((By.CLASS_NAME, self.page_conf.page_loader_css_class)))

    def wait_tableloader_not_visible(self) -> None:
        if self.page_conf.table_loader_css_class:
            self.wait.until(EC.invisibility_of_element_located((By.CLASS_NAME, self.page_conf.table_loader_css_class)))

    def wait_dialog_is_visible(self) -> None:
        attr_name = 'role'
        attr_value = 'dialog'
        search_pattern = (By.XPATH, f'//*[@{attr_name}="{attr_value}"]')
        self.wait.until(EC.visibility_of_element_located(search_pattern))

    def wait_modal_is_visible(self):
        if self.page_conf.modal_visible_css_class:
            locator = (By.XPATH, f'//*[@class="{self.page_conf.modal_visible_css_class}"]')
            self.wait.until(EC.visibility_of_element_located(locator))

    def find_element_by_data_e2e(self, value: str):
        """
        Публичный интерфейс для поиска элемента по атрибуту data-e2e.
        Использовать только в случаях, когда надо найти объект, который будет использован один раз
        (для проверок текста, ссылок и т.д.). В других случаях желательно описать элемент в классе страницы
        :param value:
        :return:
        """
        xpath = f'//*[@{config.DATA_E2E_ATTRIBUTE}="{value}"]'
        return self.find_element(By.XPATH, xpath)

    def extract_id_from_opened_url(self) -> Optional[int]:
        """
        Возвращает id, извлеченный из url текущей страницы, None, если найти не получилось
        :return:
        """
        self.check_opened()
        return get_id_from_url(self.opened_url)

    def wait_and_get_toast(self) -> Toast:
        """
        Дожидается открытия toast на странице и возвращается его
        :return:
        """
        found_toasts: List[WebElement] = self.find_elements(By.ID, Toast.component_id)
        element: WebElement = self.wait_visibility_one_of_elements(found_toasts)
        return Toast(element)

    def is_toast_success(self) -> bool:
        """
        Проверяет, что на странице появился toast и его тип success.
        Если не нужно дополнительных проверок текста уведомления, то использовать этот метод
        :return:
        """
        toast = self.wait_and_get_toast()
        return toast.is_success

    def get_confirm_dialog(self) -> ConfirmDialog:
        """
        Возвращает ConfirmDialog
        :return:
        """
        element = self.find_element(By.TAG_NAME, ConfirmDialog.tag_name)
        return ConfirmDialog(element)

    def is_toast_error(self) -> bool:
        """
        Проверяет, что на странице появился toast и его тип error
        :return:
        """
        toast = self.wait_and_get_toast()
        return toast.is_error
