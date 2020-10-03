import logging
import re
import sys

from adctest.parser.exceptions import ParserException
from lxml import html
from lxml.html import HtmlElement
from pathlib import Path
from typing import List

logger = logging.getLogger('e2e-test')

PY_EXT = 'py'


class LineRange:
    """
    Класс-хелпер, описывающий отрезок из целых чисел, включая граничные значения.
    Упрощает проверку вида c in range(a, b)
    """
    start = None
    end = None

    def __init__(self, start: int = 0, end: int = 0):
        self.start = start
        if end < start:
            raise ValueError('end must be greater than start')
        self.end = end

    def __contains__(self, line: int) -> bool:
        if not isinstance(line, int):
            raise ValueError(f'line must be integer value, got <{line}, {type(line)}>')
        if line > self.end or self.start > line:
            return False
        return True

    def __repr__(self):
        return f'<LineRange({self.start}, {self.end})>'

    def __str__(self):
        return f'range from {self.start} to {self.end}'


class Utils:
    """
    Класс, собравший основную часть хелпер-функций
    """
    @classmethod
    def get_html_from_file(cls, path: Path) -> HtmlElement:
        """
        Возвращает объект lxml.html
        :param path:
        :return:
        """
        if not path.exists():
            raise ParserException(f'path "{path}" must be exist in project dir')

        with path.open('r') as f:
            data = f.read()
            return html.fromstring(data)

    @classmethod
    def get_html_fragment_from_string(cls, data: str) -> HtmlElement:
        """
        Возвращает один тэг первого уровня из переданной строки
        :param data:
        :return:
        """
        return html.fragment_fromstring(data)

    @classmethod
    def get_class_name_from_file_name(cls, file_name: Path) -> str:
        """
        Преобразует имя файла в соответствующее ему имя класса python
        :param file_name:
        :return:
        """
        name_without_ext = file_name.stem
        new_name = cls.format_name_to_python_format(name=name_without_ext)
        name_parts = filter(lambda n: n.strip(), re.split(r'[_\W]+', new_name))
        return "".join(map(lambda s: s.capitalize(), name_parts))

    @classmethod
    def get_python_format_file_name(cls, file_name: Path) -> Path:
        """
        Преобразует имя файла в соответствующее ему имя файла py
        :param file_name:
        :return:
        """
        name_without_ext = file_name.stem
        new_name = cls.format_name_to_python_format(name=name_without_ext)
        return Path(f'{new_name}.{PY_EXT}')

    @classmethod
    def format_name_to_python_format(cls, name: str) -> str:
        """
        преобразует строку в валидное имя переменной/модуля
        :param name:
        :return:
        """
        name = name.lower()
        if name[0].isdigit():
            name = f'p{name}'
        name_parts = filter(lambda n: n.strip(), re.split(r'[-_\W]+', name))
        new_name = "_".join(name_parts)
        return new_name

    @classmethod
    def path_with_row_number(cls, path: Path, raw_number: int) -> str:
        if not raw_number or raw_number < 1:
            raw_number = 'N/A'
        return f'{path}:{raw_number}'

    @classmethod
    def make_attribute_name(cls, tag_name: str, property_name: str) -> str:
        """
        Герерирует имя атрибута класса из имени тэга и проперти, по которому осуществлялся поиск
        :param tag_name:
        :param property_name:
        :return:
        """
        tag_name = cls.format_name_to_python_format(tag_name)
        return f'{tag_name}_{property_name}'

    @classmethod
    def create_module_dir(cls, module_path: Path) -> None:
        """
        создает папку с инит файлом, если такого модуля еще нет
        :param module_path: абсолютный путь до модуля
        :return:
        """
        if not module_path.exists():
            module_path.mkdir(parents=True)
        init_file = module_path.joinpath('__init__.py')
        if not init_file.exists():
            init_file.touch()

    @classmethod
    def get_module_path_by_class(cls, target_class) -> Path:
        """
        Возвращает абсолютный путь до модуля по классу из него
        :param target_class:
        :return:
        """
        return Path(sys.modules[target_class.__module__].__file__)


class RelativeImportPath:
    """
    Класс хелпер, позволяющий построить относительный импорт классов одного модуля в другой
    исходя из их абсолютный путей
    """
    @classmethod
    def get(cls, root: Path, to_path: Path, from_path: Path, class_names: List[str]) -> str:
        """
        Генериует путь относительного импорта
        :param root: корень для обоих модулей
        :param to_path: абсолютный путь до модуля, в который нужен импорт
        :param from_path: абсолютный путь до модуля, из которого импортируется класс
        :param class_names: имена классов, который нужно импортировать
        :return:
        """
        if from_path.stem == '__init__':
            from_path = from_path.parent
        from_path_relative = from_path.relative_to(root)
        to_path_relative = to_path.relative_to(root)
        for from_part, to_part in zip(from_path_relative.parts, to_path_relative.parts):
            if from_part != to_part:
                break
            root = root.joinpath(from_part)
        from_path_relative = from_path.relative_to(root)

        dots = cls._count_dots(root, to_path)
        import_path = ''.join([dots * '.', cls._path_to_import_notation(from_path_relative)])

        printed_class_names = ', '.join(class_names)

        return f'from {import_path} import {printed_class_names}'

    @classmethod
    def _count_dots(cls, root: Path, to_path: Path) -> int:
        """
        вычисляет число точек(поддиректорий) между root и to_path
        :param root:
        :param to_path:
        :return:
        """
        base_folder = root.stem
        dots = 0
        for parent in to_path.parents:
            dots += 1
            if parent.stem.endswith(base_folder):
                break
        else:
            raise ParserException('impossible to build relative import from %s to %s', to_path, root)

        return dots

    @classmethod
    def _path_to_import_notation(cls, path: Path) -> str:
        """
        :param path: путь до модуля py
        :return:
        """
        to = []
        base = str(path.parent) if len(path.parts) > 1 else ''
        import_path = base.replace('/', '.')
        if import_path:
            to.append(import_path)

        module_name = path.stem
        to.append(module_name)

        return '.'.join(to)
