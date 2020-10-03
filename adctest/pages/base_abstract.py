"""
В классе AbstractBasePage необходимо указывать общие методы, а также обязательно методы,
которые будут вызываться в WebElementProxy, ElementDescriptor и прочих классах,
описывающих объекты, размещеные на странице
"""
import re
import time
from abc import ABCMeta, abstractmethod
from enum import Enum
from typing import List, Dict, Union, Optional, Set

from adctest.config import config
from adctest.driver.driver import E2EDriver
from adctest.page_helpers.scripts import SCROLL_TEMPLATE_SCRIPT
from adctest.helpers.exceptions import BasePageException
from adctest.helpers.utils import get_param_from_url
from adctest.pages import WebElementProxy, ElementDescriptor
from adctest.pages.uicomponents import Table
from selenium.common.exceptions import ElementNotVisibleException, NoSuchElementException, NoSuchCookieException
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait


class ScrollPositions(Enum):
    start = 'start'
    center = 'center'
    end = 'end'
    nearest = 'nearest'


class AbstractBasePage(metaclass=ABCMeta):
    _cached_attrs: Dict = None
    """Закешированные атрибуты страницы (живут пока не перезагружена страница)"""

    @abstractmethod
    def __init__(self, fresh_session: bool = False):
        """
        :param fresh_session: очищать cookie браузера
        """
        self._cached_attrs = {}
        self._driver = E2EDriver.get_driver(fresh_session=fresh_session)
        self._downloads_dir = E2EDriver.downloads_dir
        self.__wait = WebDriverWait(self._driver, config.WEB_DRIVER_WAIT)

    @abstractmethod
    def open(self, *args, **kwargs):
        ...

    def _open(self, url: str):
        # очищаем закешированные элементы при каждом обновлении страницы
        self._cached_attrs = {}
        self._driver.get(url)
        self.wait_page_loaded()

    def open_redirect_url(self, url: str):
        self._cached_attrs = {}
        self._driver.get(url)

    @property
    def driver(self):
        return self._driver

    @property
    def downloads_dir(self):
        """
        Папка, в которую Chrome будет сохранять файлы по-умолчанию. Если None, то это значит,
        что через конфиг этот параметр не был переопределен и используется папка браузера по-умолчанию
        :return:
        """
        return self._downloads_dir

    @property
    def opened_url(self):
        return self._driver.current_url

    @abstractmethod
    def check_opened(self):
        ...

    @abstractmethod
    def wait_page_loaded(self):
        ...

    @abstractmethod
    def wait_loader_not_visible(self):
        ...

    @abstractmethod
    def wait_tableloader_not_visible(self):
        ...

    def wait_loaders_hidden(self):
        self.wait_loader_not_visible()
        self.wait_tableloader_not_visible()

    def _close_tabs(self, tabs: List[str]):
        for handle in tabs:
            self.driver.switch_to.window(handle)
            self.driver.close()

    def focus_on_last_opened_tab(self):
        """
        При вызове проверяет количество открытых вкладок, ищет последнюю открытую,
        перемещает фокус драйвера на эту вкладку, а остальные закрывает.
        Не использовать напрямую без надобности, т.к. этот метод автоматически вызывается
        при вызове element.click() и element.click_and_wait()
        :return:
        """
        if len(self.driver.window_handles) > 1:
            self._cached_attrs = {}
            all_tabs: List = self.driver.window_handles
            tab_to_focus = all_tabs.pop(-1)
            self._close_tabs(all_tabs)
            self.driver.switch_to.window(tab_to_focus)

    def focus_on_first_opened_tab(self):
        """
        При вызове проверяет количество открытых вкладок и закрывает все,
        кроме первой
        :return:
        """
        if len(self.driver.window_handles) > 1:
            self._cached_attrs = {}
            all_tabs: List = self.driver.window_handles
            tab_to_focus = all_tabs.pop(0)
            self._close_tabs(all_tabs)
            self.driver.switch_to.window(tab_to_focus)

    @property
    def wait(self) -> WebDriverWait:
        """
        Стандартный объект ожидания (использовать его, если не надо ничего специфического)
        :return:
        """
        return self.__wait

    def custom_wait(self, timeout: int = None, frequency: float = None) -> WebDriverWait:
        """
        Кастомное ожидание (можно настроить частоту опроса и максимальное время ожидания)
        :param timeout:
        :param frequency:
        :return:
        """
        kwargs = {
            'timeout': config.WEB_DRIVER_WAIT,
        }
        if timeout:
            kwargs['timeout'] = timeout
        if frequency:
            kwargs['poll_frequency'] = frequency

        return WebDriverWait(self._driver, **kwargs)

    def _find_element(self, by=By.ID, value=None) -> WebElement:
        element = self._driver.find_element(by, value)
        if not element:
            raise BasePageException(f'Element not found by {by} value: "{value}"')
        return element

    def _find_elements(self, by=By.ID, value=None) -> List[WebElement]:
        elements = self._driver.find_elements(by, value)
        if not elements:
            raise BasePageException(f'Elements not found by {by} value: "{value}"')
        return elements

    def reload_element(self, el: Union[WebElementProxy, List[WebElementProxy]]) -> Union[WebElementProxy,
                                                                                         List[WebElementProxy]]:
        """
        Перегрузить элемент, если есть предположение, что он пропал из сессии
        :el: элемент, который надо перегрузить
        :return:
        """
        many = False
        if isinstance(el, list):
            el = el[0]
            many = True
        if not isinstance(el, WebElementProxy):
            raise BasePageException('Element must be instance of WebElementProxy')

        if el.attr_name:
            self._cached_attrs.pop(el.attr_name, None)

        return self.find_elements(*el.locator) if many else self.find_element(*el.locator)

    def find_element(self, by=By.ID, value=None) -> WebElementProxy:
        """
        Публичный интерфейс для поиска уникального объекта на странице по любому паттерну.
        !!! Использовать только в случаях, когда надо найти объект, который будет использован один раз
        (для проверок текста, ссылок и т.д.). В других случаях желательно описать элемент в классе страницы
        :param by:
        :param value:
        :return:
        """
        element = self._find_element(by, value)
        return self._wrap_proxy(element, by, value)

    def find_elements(self, by=By.ID, value=None) -> List[WebElementProxy]:
        """
        Публичный интерфейс для поиска нескольких объектов на странице, соответствующих одному паттерну.
        !!! Использовать только в случаях, когда надо найти объект, который будет использован один раз
        (для проверок текста, ссылок и т.д.). В других случаях желательно описать элемент в классе страницы
        :param by:
        :param value:
        :return:
        """
        elements = self._find_elements(by, value)
        return [self._wrap_proxy(el, by, value) for el in elements]

    def _wrap_proxy(self, element: WebElement, by, value) -> WebElementProxy:
        """
        Оборачивает инстанс WebElement, чтобы были доступны кастомные функции WebElementProxy
        :param element:
        :param by:
        :param value:
        :return:
        """
        return WebElementProxy(
            target_object=element,
            page=self,
            by=by,
            value=value,
        )

    def scroll_to_element(self, element: WebElementProxy, vertical_position: ScrollPositions = ScrollPositions.center,
                          horizontal_position: ScrollPositions = ScrollPositions.nearest):
        """
        Скроллит страницу к переданному элементу
        :param element: Элемент, до которого скроллить
        :param vertical_position: Позиция скролла по вертикали
        :param horizontal_position: Позиция скролла по горизонтали
        :return:
        """
        script = SCROLL_TEMPLATE_SCRIPT.format(block=vertical_position.value, inline=horizontal_position.value)
        self.driver.execute_script(script, element)

    @classmethod
    def wait_visibility_one_of_elements(cls, elements: List[Union[WebElementProxy, WebElement]],
                                        timeout: Optional[int] = None,
                                        ticks: Optional[float] = 0.5) -> Union[WebElementProxy, WebElement]:
        """
        Ожидает пока один из переданных элементов станет видимым для пользователя (находится в DOM, имеет размер)
        :param elements: Список элементов для ожидания
        :param timeout: максимальное время ожидания
        :param ticks: частота проверок (по умолчанию - раз в пол секунды)
        :return:
        """
        if not elements:
            raise NoSuchElementException('Nothing to wait. At least one element must be passed')
        timeout = timeout or config.WEB_DRIVER_WAIT
        run_time = timeout

        while run_time > 0:
            for el in elements:
                if el.is_displayed():
                    return el
            time.sleep(ticks)
            run_time -= ticks
        raise ElementNotVisibleException('Could not wait for the visibility of any of transmitted elements')

    def delete_cookies(self, filter_value: Optional[str] = None, cookie_key: str = 'name') -> None:
        """
        Clear cookies in current browser session
        :param filter_value: clear all browser cookies for current domain if it not passed. Value support regex
        :param cookie_key: key of cookie to clear. Name of cookie by default
        :return:
        """
        if filter_value is None:
            self.driver.delete_all_cookies()
        else:
            cookies: Set[Dict] = self.driver.get_cookies()
            for item in cookies:
                try:
                    cookie_value = item[cookie_key]
                except KeyError:
                    raise NoSuchCookieException(f'Not found cookie by (value, key) = ({filter_value}, {cookie_key})')
                if re.search(filter_value, cookie_value, flags=re.IGNORECASE):
                    self.driver.delete_cookie(name=item['name'])

    def delete_local_storage(self, key: Optional[str] = None) -> None:
        """
        Clear local storage in current browser session
        :param key: clear all browser local storage if it not passed. Value support regex
        :return:
        """
        if key:
            self.driver.execute_script("window.localStorage.removeItem(arguments[0]);", key)
        else:
            self.driver.execute_script("window.localStorage.clear();")

    def wait_accessibility_of(self, element_descriptor: Union[ElementDescriptor, WebElementProxy, Table],
                              timeout: int = None, frequency: float = 0.2) -> None:
        """
        Ждет пока элемент появится на странице
        :param element_descriptor:  дескриптор элемента
        :param timeout: максимальное время ожидания (в секундах)
        :param frequency: частота опросов (в секундах)
        :return:
        """
        if not isinstance(element_descriptor, (ElementDescriptor, Table)):
            raise BasePageException('It wait only Element Descriptor instance objects')
        search_pattern = (element_descriptor.search_by, element_descriptor.value)
        self.custom_wait(timeout, frequency).until(EC.visibility_of_element_located(search_pattern))

    def extract_param_from_opened_url(self, name: str) -> Optional[str]:
        """
        Возвращает param, извлеченный из url текущей страницы, None, если найти не получилось
        :param name:
        :return:
        """
        self.check_opened()
        res = get_param_from_url(url=self.opened_url, param_name=name)
        if res:
            return res[0]
