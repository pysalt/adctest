from adctest.helpers.exceptions import PageNotOpened
from adctest.helpers.utils import get_param_from_url
from adctest.pages.base_abstract import AbstractBasePage


class BaseLandingPage(AbstractBasePage):
    page_url = None
    """Адрес, на котором открывается лендинг"""
    check_param = None
    """Имя параметра, по которому проверяем, что оказались на правильной странице"""

    def __init__(self, page_url: str, fresh_session: bool = False, open_page: bool = True):
        """

        :param page_url: url - ленда/приленда
        :param fresh_session: нужно ли очищать текущую сессию браузера (удалить куки и прочее)
        :param open_page: Если передать False, то будет создан объект без открытия страницы в браузере
        """
        super().__init__(fresh_session=fresh_session)
        self.page_url = page_url
        if open_page:
            self.open()

    def open(self):
        self._open(url=self.page_url)
        self.check_opened()

    def check_opened(self):
        param = get_param_from_url(self.opened_url, self.check_param)
        expected_param = get_param_from_url(self.page_url, self.check_param)
        if param and expected_param and param[0] == expected_param[0]:
            return
        raise PageNotOpened(f'Get attr of {type(self).__name__}, but current url: {self.opened_url}')

    def wait_page_loaded(self):
        pass

    def wait_loader_not_visible(self):
        pass

    def wait_tableloader_not_visible(self):
        pass

    def validate_domain(self, name: str):
        """
        Проверяет, что текущая страница открыта на домене name
        :param name: Имя домена
        :return:
        """
        if name not in self.opened_url:
            raise PageNotOpened(f'Expect domain {name}, but current url: {self.opened_url}')
