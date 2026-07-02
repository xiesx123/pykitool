from contextlib import contextmanager

import sqlmodel
from pydantic import ConfigDict
from sqlalchemy import func
from sqlalchemy.engine import Engine
from sqlalchemy.sql import Select
from sqlmodel import SQLModel, select, text
from sqlmodel.sql.expression import SelectOfScalar
from typing_extensions import Any, Dict, List, Optional, Tuple, Union


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

    @classmethod
    def set_engine(cls, engine: Engine) -> None:
        cls.__engines__[cls.__get_scope] = engine

    @classmethod
    def get_engine(cls) -> Engine:
        return cls.__engines__.get(cls.__get_scope)

    @classmethod
    def create_tables(cls, *args, **kwargs):
        cls.metadata.create_all(cls.__engines__.get(cls.__get_scope), *args, **kwargs)

    @classmethod
    def find_by_id(
        cls,
        ident: Union[Dict[str, Any], Tuple[Any], Any],
        session: Optional[sqlmodel.Session] = None,
    ):
        """根据主键查询记录，支持传入已有 session 以复用事务。"""
        if session is not None:
            return session.get(cls, ident)
        with cls.Session() as s:
            return s.get(cls, ident)

    def insert(self, session: Optional[sqlmodel.Session] = None):
        """插入新记录，支持传入已有 session 以复用事务。"""
        if session is not None:
            session.add(self)
            session.flush()
            session.refresh(self)
            return self
        with self.__class__.Session() as s:
            s.add(self)
            s.commit()
            s.refresh(self)
        return self

    def update(self, session: Optional[sqlmodel.Session] = None):
        """更新已有记录，支持传入已有 session 以复用事务。"""
        if session is not None:
            updated = session.merge(self)
            session.flush()
            session.refresh(updated)
            return updated
        with self.__class__.Session() as s:
            updated = s.merge(self)
            s.commit()
            s.refresh(updated)
        return updated

    def upsert(self, session: Optional[sqlmodel.Session] = None):
        """根据主键是否有值自动选择 create 或 update。"""
        # 获取主键字段名列表
        pk_fields = self.__class__.__table__.primary_key.columns.keys()
        has_pk = all(getattr(self, pk, None) is not None for pk in pk_fields)
        if has_pk:
            return self.update(session=session)
        else:
            return self.insert(session=session)

    def delete(self, session: Optional[sqlmodel.Session] = None):
        """删除记录，支持传入已有 session 以复用事务。"""
        if session is not None:
            obj = session.merge(self)
            session.delete(obj)
            session.flush()
            return self
        with self.__class__.Session() as s:
            obj = s.merge(self)
            s.delete(obj)
            s.commit()
        return self

    @classmethod
    def delete_by_ids(cls, ids: List) -> int:
        """批量删除记录（原子事务），传入主键 id 列表，返回实际删除行数。"""
        rows = 0
        with cls.transaction() as session:
            for oid in ids:
                obj = session.get(cls, oid)
                if obj:
                    session.delete(obj)
                    rows += 1
        return rows

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
        engine: Optional[Engine] = cls.__engines__.get(cls.__get_scope)
        if engine is None:
            raise EngineException("Engine is not initialized. Use `.set_engine` method to set engine.")
        return sqlmodel.Session(bind=engine)

    @classmethod
    @contextmanager
    def transaction(cls):
        """
        事务上下文管理器，yield 一个 session，自动提交或回滚。

        用法::

            with UserTable.transaction() as session:
                user.create(session=session)
                order.create(session=session)
                # 任何异常都会自动回滚
        """
        with cls.Session() as session:
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise

    @classproperty
    def select(cls) -> SelectOfScalar:
        return select(cls)

    @classproperty
    def __get_scope(cls) -> str:
        return str(cls.__scope__) if hasattr(cls, "__scope__") else "default"


# 查询
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

    @property
    def count(self) -> int:
        """返回查询结果总数，使用子查询 COUNT，不加载全量数据。"""
        with self.model_cls.Session() as session:
            count_stmt = select(func.count()).select_from(self.statement.subquery())
            return session.execute(count_stmt).scalar() or 0

    def paginate(self, offset: int, limit: int) -> Tuple[List, int]:
        """
        分页查询，返回 (items, total) 元组。

        内部使用 COUNT 子查询统计总数，不加载全量数据。

        用法::

            users, total = UserTable.query(stmt).paginate(offset=0, limit=20)

        Args:
            offset: 跳过的记录数
            limit:  每页记录数

        Returns:
            tuple: (items: list, total: int)
        """
        with self.model_cls.Session() as session:
            count_stmt = select(func.count()).select_from(self.statement.subquery())
            total = session.execute(count_stmt).scalar() or 0
            items = session.exec(self.statement.offset(offset).limit(limit), params=self.params).all()
        return list(items), total


# 逻辑删除
class SoftDelete:

    # 自动过滤已删除记录，替代每次手写 .where(is_delete == 0)
    @classproperty
    def select_active(cls) -> SelectOfScalar:
        return select(cls).where(cls.is_delete == 0)

    # 软删除单条记录（设 is_delete=1）
    def soft_delete(self, session=None):
        self.is_delete = 1
        return self.update(session=session)

    @classmethod
    def soft_delete_by_ids(cls, ids: List, skip_check=None) -> Tuple[int, List]:
        """
        批量软删除（原子事务）。

        - 自动跳过已删除记录
        - skip_check: callable(obj) -> bool，返回 True 则跳过该记录
        - 返回 (rows, deleted_list)

        用法::

            rows, deleted = UserTable.soft_delete_by_ids(
                ids, skip_check=lambda u: u.role == Role.SUPER_ADMIN
            )
        """
        rows = 0
        deleted = []
        with cls.transaction() as session:
            for id in ids:
                obj = session.get(cls, id)
                if not obj or obj.is_delete == 1:
                    continue
                if skip_check and skip_check(obj):
                    continue
                obj.is_delete = 1
                session.add(obj)
                deleted.append(obj)
                rows += 1
        return rows, deleted


__all__ = ["EngineException", "SQLModelPlus", "SoftDelete"]
