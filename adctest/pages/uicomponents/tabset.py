from adctest.helpers.exceptions import TabSetException
from adctest.pages import WebElementProxy
from selenium.common.exceptions import NoSuchElementException


class TabView:
    """
    Класс-хелпер для работы с элементами интерфейса типа TabView (в ангуляре: p-tabView).
    Реализует интерфейсы для выбора элемента из списка.

    пример использования:
    page = SomePage()
    tab_set = TabView(page.tab_view_payments)
    """
    _tag_name = 'p-tabview'
    _selected_tab_xpath = '//*[contains(@class, "ui-tabview-selected")]'
    _tab_xpath = '//a[@role="tab"]'
    _xpath_by_index_template = '//a[@aria-controls="ui-tabpanel-{index}"]'
    _xpath_by_visible_text_template = '//a[@role="tab" and contains(string(),"{text}")]'

    def __init__(self, element: WebElementProxy):
        """
        Сохраняет внутри себя инстанс WebElementProxy и проводит необходимые проверки
        :param element:
        """
        if element.tag_name.lower() != self._tag_name:
            raise TabSetException(f'{self.__class__} only works on <{self._tag_name}> elements, not on <{element.tag_name}>')
        if not isinstance(element, WebElementProxy):
            raise TabSetException(f'{self.__class__} work only with WebElementProxy instance, not {element.__class__}')
        self._el = element

    def select_by_index(self, index: int):
        """
        starts from 0
        :param index:
        :return:
        """
        xpath = self._xpath_by_index_template.format(index=index)
        self._open_tab(xpath)

    def select_by_text(self, text: str):
        """
        Uniq part of tab's text
        :param text:
        :return:
        """
        xpath = self._xpath_by_visible_text_template.format(text=text)
        self._open_tab(xpath)

    def _open_tab(self, xpath: str):
        tab = self._get_child_by_xpath(xpath)
        tab.click()
        self._el.page.wait_loaders_hidden()

    def _get_child_by_xpath(self, xpath: str):
        try:
            return self._el.find_element_by_xpath(xpath)
        except NoSuchElementException:
            raise TabSetException('Cannot find selected tab')

    @property
    def selected_tab_text(self):
        tab = self._get_child_by_xpath(self._selected_tab_xpath)
        return tab.text


class TabSet(TabView):
    """
    Класс-хелпер для работы с элементами интерфейса типа TabSet (в ангуляре: tabset).
    Реализует интерфейсы для выбора элемента из списка.

    пример использования:
    page = SomePage()
    tab_set = TabSet(page.tab_set_payments)
    """
    _tag_name = 'tabset'
    _selected_tab_xpath = '//*[contains(@class, "nav-item active")]'
    _tab_xpath = '//a[contains(@class, "nav-link")]'
    _xpath_by_index_template = None
    _xpath_by_visible_text_template = '//a[contains(@class, "nav-link") and contains(text(),"{text}")]'

    def select_by_index(self, index: int):
        raise NotImplemented('Not implemented for TabSet')
