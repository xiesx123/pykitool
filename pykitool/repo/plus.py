from __future__ import annotations

from contextlib import contextmanager

import sqlmodel
from pydantic import ConfigDict
from sqlalchemy import func
from sqlalchemy.engine import Engine
from sqlalchemy.sql import Select
from sqlmodel import Session, SQLModel, delete, func, select, text, update
from sqlmodel.sql.expression import SelectOfScalar
from typing_extensions import Any, Dict, List, Optional, Tuple, Union, overload

from pykitool.base.result import PR
from pykitool.core.exception import ExcCode, RuntimeException
from pykitool.repo.exception import EngineException


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


# 公共查询
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
        """执行查询，返回所有匹配记录的列表。

        用法::

            users = UserTable.query(UserTable.select().where(UserTable.age > 18)).all
        """
        with self.model_cls.Session() as session:
            return session.exec(self.statement, params=self.params).all()

    @property
    def first(self):
        """执行查询，返回第一条匹配记录，无结果时返回 None。

        用法::

            user = UserTable.query(UserTable.select().where(UserTable.name == "Alice")).first
        """
        with self.model_cls.Session() as session:
            return session.exec(self.statement, params=self.params).first()

    @property
    def count(self) -> int:
        """返回查询结果总数，使用子查询 COUNT，不加载全量数据。

        用法::

            total = UserTable.query(UserTable.select().where(UserTable.age > 18)).count
        """
        with self.model_cls.Session() as session:
            count_stmt = select(func.count()).select_from(self.statement.subquery())
            return session.execute(count_stmt).scalar() or 0

    @overload
    def paginate(self, offset: int, limit: int) -> Tuple[List, int]: ...
    @overload
    def paginate(self, offset: int, limit: int, order_by: str, desc: bool = ...) -> Tuple[List, int]: ...
    def paginate(self, offset: int, limit: int, order_by: Optional[str] = None, desc: bool = False) -> Tuple[List, int]:
        """
        分页查询，返回 (items, total) 元组。

        内部使用 COUNT 子查询统计总数，不加载全量数据。

        用法::

            # 基本分页
            users, total = UserTable.query(stmt).paginate(offset=0, limit=20)
            # 带排序
            users, total = UserTable.query(stmt).paginate(offset=0, limit=20, order_by="created_at", desc=True)

        Args:
            offset:   跳过的记录数
            limit:    每页记录数
            order_by: 排序字段名（模型属性名），不传则不排序
            desc:     是否降序，默认 False（升序）

        Returns:
            tuple: (items: list, total: int)
        """
        with self.model_cls.Session() as session:
            count_stmt = select(func.count()).select_from(self.statement.subquery())
            total = session.execute(count_stmt).scalar() or 0
            stmt = self.statement
            if order_by is not None:
                col = getattr(self.model_cls, order_by)
                stmt = stmt.order_by(col.desc() if desc else col)
            items = session.exec(stmt.offset(offset).limit(limit), params=self.params).all()
        return list(items), total

    @overload
    def paginate_pr(self, offset: int, limit: int) -> Any: ...
    @overload
    def paginate_pr(self, offset: int, limit: int, order_by: str, desc: bool = ...) -> Any: ...
    def paginate_pr(self, offset: int, limit: int, order_by: Optional[str] = None, desc: bool = False):
        """
        分页查询，直接返回 PResult 对象（PR.success 包装）。

        用法::

            # 基本分页
            result = UserTable.query(stmt).paginate_pr(offset=0, limit=20)
            # 带排序
            result = UserTable.query(stmt).paginate_pr(offset=0, limit=20, order_by="created_at", desc=True)
            # result.data  → 当页数据列表
            # result.count → 总记录数

        Args:
            offset:   跳过的记录数
            limit:    每页记录数
            order_by: 排序字段名（模型属性名），不传则不排序
            desc:     是否降序，默认 False（升序）

        Returns:
            PResult: 包含 data 和 count 字段的分页结果对象
        """
        items, total = self.paginate(offset=offset, limit=limit, order_by=order_by, desc=desc)
        return PR.success(data=items, count=total)


# 逻辑删除
class SoftDelete:

    @classmethod
    def select_active(cls) -> SelectOfScalar:
        """返回只包含未删除记录的查询语句（is_delete == 0）。

        用法::

            users = UserTable.select_active().where(UserTable.age > 18)
            result = UserTable.query(users).all
        """
        return select(cls).where(cls.is_delete == 0)  # type: ignore[attr-defined]

    @classmethod
    def soft_delete_by_ids(cls, ids: List, skip_check=None) -> Tuple[int, List]:
        """
        批量软删除（原子事务）。

        - 自动跳过已删除记录
        - skip_check: callable(obj) -> bool，返回 True 则跳过该记录
        - 返回 (rows, deleted_list)

        用法::

            rows, deleted = UserTable.soft_delete_by_ids(
                ids, skip_check=lambda u: u.role == Role.ADMIN
            )
        """
        rows = 0
        deleted = []
        with cls.Transaction() as session:
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

    # AR增强：实例方法

    def soft_delete(self, session=None):
        """软删除当前实例（设 is_delete=1），支持传入已有 session 以复用事务。

        用法::

            user.soft_delete()
            # 或在事务中
            with UserTable.Transaction() as session:
                user.soft_delete(session=session)
        """
        self.is_delete = 1
        return self.update(session=session)


# AR增强
class SQLModelPlus(SQLModel):
    model_config = ConfigDict(ignored_types=(_ClassPropertyDescriptor,))

    __engines__: Dict[str, Engine] = {}

    @classproperty
    def __get_scope(cls) -> str:
        return str(cls.__scope__) if hasattr(cls, "__scope__") else "default"

    @classmethod
    def set_engine(cls, engine: Engine) -> None:
        """绑定数据库引擎，支持多租户通过 __scope__ 隔离。

        用法::

            engine = sqlmodel.create_engine(config.get_database(), echo=False)
            SQLModelPlus.set_engine(engine)
        """
        cls.__engines__[cls.__get_scope] = engine

    @classmethod
    def get_engine(cls) -> Engine:
        """获取当前 scope 对应的数据库引擎。"""
        return cls.__engines__.get(cls.__get_scope)

    @classmethod
    def create_tables(cls, *args, **kwargs):
        """根据所有已注册的 SQLModel 子类元数据在数据库中创建表（若不存在）。

        需在所有 Table 类导入后调用，以确保 SQLModel 元数据已完整注册。

        用法::

            # 导入所有 Table 类触发 SQLModel 元数据注册
            from app.models import UserTable, OrderTable  # noqa: F401
            SQLModelPlus.create_tables()
        """
        cls.metadata.create_all(cls.__engines__.get(cls.__get_scope), *args, **kwargs)

    @classmethod
    def Session(cls) -> sqlmodel.Session:
        engine: Optional[Engine] = cls.__engines__.get(cls.__get_scope)
        if engine is None:
            raise EngineException("Engine is not initialized. Use `.set_engine` method to set engine.")
        return sqlmodel.Session(bind=engine)

    @classmethod
    @contextmanager
    def Transaction(cls):
        """
        事务上下文管理器，yield 一个 session，自动提交或回滚。

        用法::

            with UserTable.Transaction() as session:
                user.upsert(session=session)
                order.upsert(session=session)
                # 任何异常都会自动回滚
        """
        with cls.Session() as session:
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise

    @classmethod
    def select(cls) -> SelectOfScalar:
        """返回针对当前模型的基础查询语句，可继续链式调用 .where() 等条件。

        用法::

            stmt = UserTable.select().where(UserTable.age > 18)
            users = UserTable.query(stmt).all
        """
        return select(cls)

    @classmethod
    def query(cls, statement: Union[SelectOfScalar, str], params: Union[Dict[str, Any], Tuple[Any]] = {}):
        """包装查询语句，返回 Query 对象，支持 .all / .first / .count / .paginate。

        用法::

            # 使用 SelectOfScalar
            result = UserTable.query(UserTable.select().where(UserTable.name == "Alice")).first
            # 使用原生 SQL
            result = UserTable.query("SELECT * FROM user WHERE id = :id", params={"id": 1}).first
        """
        return Query(model_cls=cls, statement=statement, params=params)

    @classmethod
    def find_by_id(cls, ident: Union[Dict[str, Any], Tuple[Any], Any], session: Optional[sqlmodel.Session] = None):
        """根据主键查询记录，查不到时返回 None，支持传入已有 session 以复用事务。

        用法::

            user = UserTable.find_by_id(1)
            # 在事务中复用 session
            with UserTable.Transaction() as session:
                user = UserTable.find_by_id(1, session=session)
        """
        if session is not None:
            return session.get(cls, ident)
        with cls.Session() as s:
            return s.get(cls, ident)

    @classmethod
    def find_by_id_or_raise(cls, ident: Union[Dict[str, Any], Tuple[Any], Any], session: Optional[sqlmodel.Session] = None, message: Optional[str] = None):
        """根据主键查询记录，查不到时抛出 RuntimeException。

        用法::

            user = UserTable.find_by_id_or_raise(1)
            user = UserTable.find_by_id_or_raise(1, message="用户不存在")
        """
        obj = cls.find_by_id(ident, session=session)
        if obj is None:
            raise RuntimeException(code=ExcCode.DBASE, message=message or f"{cls.__name__} not found")
        return obj

    @classmethod
    def update_by_id(cls, ident: Union[Dict[str, Any], Tuple[Any], Any], **kwargs) -> bool:
        """根据主键更新指定字段，返回是否成功（True=更新成功，False=主键列不存在）。

        用法::

            UserTable.update_by_id(1, name="新名字", age=18)
            # 复合主键
            UserTable.update_by_id({"user_id": 1, "role_id": 2}, status=0)
        """
        pk_cols = list(cls.__table__.primary_key.columns)
        if not pk_cols:
            return False
        if len(pk_cols) == 1:
            where_clause = pk_cols[0] == ident
        else:
            where_clause = sqlmodel.and_(*(col == ident[col.name] for col in pk_cols))
        stmt = update(cls).where(where_clause).values(**kwargs)
        with cls.Transaction() as session:
            result = session.exec(stmt)
        return result.rowcount > 0

    @classmethod
    def delete_by_id(cls, ident: Union[Dict[str, Any], Tuple[Any], Any]) -> bool:
        """根据主键删除单条记录，返回是否成功删除（True=找到并删除，False=未找到）。

        用法::

            deleted = UserTable.delete_by_id(1)
        """
        with cls.Transaction() as session:
            obj = session.get(cls, ident)
            if obj:
                session.delete(obj)
                return True
        return False

    @classmethod
    def delete_by_ids(cls, ids: List) -> int:
        """批量删除记录（原子事务），传入主键 id 列表，返回实际删除行数。

        用法::

            rows = UserTable.delete_by_ids([1, 2, 3])
        """
        rows = 0
        with cls.Transaction() as session:
            for oid in ids:
                obj = session.get(cls, oid)
                if obj:
                    session.delete(obj)
                    rows += 1
        return rows

    @classmethod
    def truncate(cls) -> None:
        """清空表中所有数据，比 delete_all 效率更高（不记录逐行日志）。

        SQLite 不支持 TRUNCATE，自动回退为 DELETE FROM。

        用法::

            UserTable.truncate()

        .. warning::
            此操作不可恢复，执行前请确认。
        """
        dialect = cls.get_engine().dialect.name
        table_name = cls.__tablename__
        with cls.Session() as session:
            if dialect == "sqlite":
                session.exec(text(f"DELETE FROM {table_name}"))
            else:
                session.exec(text(f"TRUNCATE TABLE {table_name}"))
            session.commit()

    # AR增强：实例方法

    def insert(self, session: Optional[sqlmodel.Session] = None):
        """插入新记录，自动 flush + refresh 返回最新实例，支持传入已有 session 以复用事务。

        用法::

            user = UserTable(name="Alice", age=18).insert()
            # 在事务中复用 session
            with UserTable.Transaction() as session:
                user = UserTable(name="Alice").insert(session=session)
        """
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
        """将当前实例的字段变更持久化到数据库，自动 merge + refresh 返回最新实例，支持传入已有 session 以复用事务。

        用法::

            user.name = "Bob"
            user = user.update()
            # 在事务中复用 session
            with UserTable.Transaction() as session:
                user = user.update(session=session)
        """
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
        """根据主键是否有值自动选择 insert 或 update，支持传入已有 session 以复用事务。

        用法::

            # 无主键 → insert
            user = UserTable(name="Alice").upsert()
            # 有主键 → update
            user.name = "Bob"
            user = user.upsert()
        """
        pk_fields = self.__class__.__table__.primary_key.columns.keys()
        has_pk = all(getattr(self, pk, None) is not None for pk in pk_fields)
        if has_pk:
            return self.update(session=session)
        else:
            return self.insert(session=session)

    def delete(self, session: Optional[sqlmodel.Session] = None):
        """从数据库中删除当前实例，支持传入已有 session 以复用事务。

        用法::

            user.delete()
            # 在事务中复用 session
            with UserTable.Transaction() as session:
                user.delete(session=session)
        """
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
