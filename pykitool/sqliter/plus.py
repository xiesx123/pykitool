from typing import Any, Dict, Tuple, Union

import sqlmodel
from pydantic import ConfigDict
from sqlalchemy.engine import Engine
from sqlalchemy.sql import Select
from sqlmodel import SQLModel, select, text
from sqlmodel.sql.expression import SelectOfScalar


class EngineException(Exception):
    pass


# 类属性描述符：兼容 Python 3.13 移除 @classmethod + @property 链式用法
class _ClassPropertyDescriptor:
    def __init__(self, func):
        self.func = func

    def __get__(self, obj, cls=None):
        if cls is None:
            cls = type(obj)
        return self.func(cls)


def classproperty(func):
    return _ClassPropertyDescriptor(func)


class SQLModelPlus(SQLModel):
    model_config = ConfigDict(ignored_types=(_ClassPropertyDescriptor,))

    __engines__: Dict[str, Engine] = {}

    @classproperty
    def __get_scope(cls) -> str:
        return str(cls.__scope__) if hasattr(cls, "__scope__") else "default"

    @classmethod
    def create_tables(cls, *args, **kwargs):
        cls.metadata.create_all(cls.__engines__.get(cls.__get_scope), *args, **kwargs)

    @classmethod
    def find_by_id(cls, ident: Union[Dict[str, Any], Tuple[Any], Any]):
        with cls.Session() as session:
            return session.get(cls, ident)

    def save(self):
        try:
            return self.create()
        except:
            return self.update()

    def create(self):
        with self.__class__.Session() as session:
            session.add(self)
            session.commit()
            session.refresh(self)
        return self

    def update(self):
        with self.__class__.Session() as session:
            updated_instance = session.merge(self)
            session.commit()
            session.refresh(updated_instance)
        return updated_instance

    def delete(self):
        with self.__class__.Session() as session:
            session.delete(self)
            session.commit()
        return self

    @classmethod
    def set_engine(cls, engine: Engine) -> None:
        cls.__engines__[cls.__get_scope] = engine

    @classmethod
    def get_engine(cls) -> Engine:
        return cls.__engines__.get(cls.__get_scope)

    @classmethod
    def query(
        cls,
        statement: Union[SelectOfScalar, str],
        params: Union[Dict[str, Any], Tuple[Any]] = {},
    ):
        return Query(model_cls=cls, statement=statement, params=params)

    # 获取数据库 Session 实例
    @classmethod
    def Session(cls) -> sqlmodel.Session:
        engine: Engine | None = cls.__engines__.get(cls.__get_scope)
        if engine is None:
            raise EngineException("Engine is not initialized. Use `.set_engine` method to set engine.")
        return sqlmodel.Session(bind=engine)

    @classproperty
    def select(cls) -> SelectOfScalar:
        return select(cls)


class Query:
    def __init__(
        self,
        model_cls: SQLModelPlus,
        statement: Union[SelectOfScalar, str],
        params: Union[Dict[str, Any], Tuple[Any], None] = None,
    ):
        self.model_cls = model_cls
        self.statement = statement if isinstance(statement, (SelectOfScalar, Select)) else text(statement)
        self.params = params

    @property
    def all(self):
        with self.model_cls.Session() as session:
            return session.exec(self.statement, params=self.params).all()

    @property
    def first(self):
        with self.model_cls.Session() as session:
            return session.exec(self.statement, params=self.params).first()


__all__ = ["SQLModelPlus", "EngineException"]
