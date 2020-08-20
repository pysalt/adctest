import os
from decimal import Decimal
from typing import List, Dict, Optional, Any

from adctest.helpers.funs import str_or_bool

SUPPORTED_TYPES = (str, int, float, Decimal, bool, )


class ConfigException(Exception):
    def __init__(self, msg: str, *args):
        formatted_msg = msg.format(*args)
        super().__init__(formatted_msg)


class BaseConfigMeta(type):
    def __new__(mcs, class_name, bases, attrs):
        if class_name != 'BaseConfig':
            mcs._validate_attribute(attrs)
        return type.__new__(mcs, class_name, bases, attrs)

    @classmethod
    def _validate_attribute(mcs, attrs: Dict, prev_name: Optional[str] = ''):
        for name, value in attrs.items():
            if name.startswith('_') or callable(value):
                continue
            if isinstance(value, dict):
                mcs._validate_attribute(value, prev_name=prev_name)
                continue
            if not isinstance(value, SUPPORTED_TYPES):
                full_name = '.'.join(filter(lambda o: o, [prev_name, name]))
                raise ConfigException('Config attribute {} have unsupported type {}', full_name, type(value))


class BaseConfig(metaclass=BaseConfigMeta):
    UPDATE_FROM_ENV = False
    ENV_KEY_PREFIX = None

    def __init__(self, *args, **kwargs):
        if self.UPDATE_FROM_ENV:
            if self.ENV_KEY_PREFIX is None:
                raise RuntimeError('ENV_KEY_PREFIX must be specified if UPDATE_FROM_ENV==True')
            self.update_from_env()

    def update_from_custom_config(self, class_: 'BaseConfig'):
        pass

    def update_from_env(self):
        """
        Переопределяет атрибуты конфига из переменных окружения
        :return:
        """
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
