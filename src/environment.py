import json
from os import environ
from typing import Dict, Optional, Any

import boto3
from dotenv import load_dotenv
from injector import singleton

load_dotenv()


@singleton
class Environment:
    __secret: Optional[Dict[str, Any]] = None

    def get_str(self, name: str) -> Optional[str]:
        value = self.__get(name)
        if isinstance(value, str):
            return value
        raise TypeError(f'Expected a string value, got {type(value).__name__}')

    def __get(self, name: str) -> Optional[Any]:
        if self.__secret is None:
            secret_arn = environ.get('SECRET_ARN')
            self.__secret = self.__import_from(secret_arn) if secret_arn else {}
        return self.__secret.get(name, environ.get(name))

    @staticmethod
    def __import_from(secret_arn: str) -> Dict[str, str]:
        secret_string = boto3.client('secretsmanager').get_secret_value(SecretId=secret_arn)['SecretString']
        try:
            return json.loads(secret_string)
        except json.JSONDecodeError:
            return {}
