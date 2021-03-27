import os
from decimal import Decimal
from typing import List, Dict, Optional, Any

from adctest.helpers.funs import str_or_bool

SUPPORTED_TYPES = (str, int, float, Decimal, bool, )


class ConfigException(Exception):
    def __init__(self, msg: str, *args):
        formatted_msg = msg.format(*args)
        super().__init__(formatted_msg)


class BaseConfig(object):
    UPDATE_FROM_ENV: bool = False
    ENV_KEY_PREFIX: Optional[str] = None

    def __init__(self, *args, **kwargs):
        self._validate_attribute()
        if self.UPDATE_FROM_ENV:
            self.update_from_env()

    def _validate_attribute(self):
        for name, value in self.__dict__.items():
            if name.startswith('_') or callable(value):
                continue
            if not isinstance(value, SUPPORTED_TYPES):
                raise ConfigException('Config attribute {} have unsupported type {}', name, type(value))

    def update_from_custom_dict_config(self, config_: Dict):
        """
        Call this method before collecting tests
        :param config_:
        :return:
        """
        for name, attr in config_.items():
            if not name.startswith('_') and not callable(attr):
                setattr(self, name, attr)
        if self.UPDATE_FROM_ENV:
            self.update_from_env()

    def update_from_env(self):
        """
        Переопределяет атрибуты конфига из переменных окружения
        :return:
        """
        if self.ENV_KEY_PREFIX is None:
            raise RuntimeError('ENV_KEY_PREFIX must be specified if UPDATE_FROM_ENV==True')
        used = []
        print('Startupdating e2e-config from environ')
        for key, value in os.environ.items():
            if key.startswith(self.ENV_KEY_PREFIX):
                try:
                    attr_name, *dct_keys = key[len(self.ENV_KEY_PREFIX) + 2:].split('__')
                    self._update_attribute(attr_name=attr_name, dct_keys=dct_keys, value=value)
                except Exception as ex:
                    print('Cannot update e2e-config from environ value (it skipped): \n', key, str(ex))
                    continue
                used.append(key)
        print('Attributes parsed from environ:\n', used)

    @classmethod
    def _convert_value_type_from_exist(cls, exist_value: Any, new_value: str):
        converter = type(exist_value)
        if converter is bool:
            converter = str_or_bool
        return converter(new_value)

    def _update_attribute(self, attr_name, dct_keys: List, value):
        attr = getattr(self, attr_name)
        if not dct_keys:
            setattr(self, attr_name, self._convert_value_type_from_exist(attr, value))
        else:
            self._recursive_update_value_in_dict(attr, dct_keys, value)

    @classmethod
    def _recursive_update_value_in_dict(cls, base_dct: Dict, dct_vector: List, value):
        if len(dct_vector) > 1:
            key = dct_vector.pop(0)
            return cls._recursive_update_value_in_dict(base_dct[key], dct_vector, value)
        key = dct_vector[0]
        if isinstance(base_dct[key], dict):
            raise ConfigException('Cannot replace attribute of dict type from environ')
        base_dct[key] = cls._convert_value_type_from_exist(base_dct[key], value)


class ConfigAttrsMeta(type):
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
        config_class = bases[0]
        new_attrs = {}
        for name, attr in config_class.__dict__.items():
            if not name.startswith('_') and not callable(attr):
                new_attrs[name] = name

        new_class = type.__new__(mcs, class_name, tuple(), new_attrs)

        return new_class
