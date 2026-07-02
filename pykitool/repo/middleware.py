import time
from contextvars import ContextVar
from typing import Dict, Optional, Union

from loguru import logger
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.engine.url import URL
from sqlalchemy.orm import sessionmaker as sessionmaker_
from sqlmodel import Session, create_engine
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.types import ASGIApp

from pykitool.repo.exception import MissingSessionError, SessionNotInitialisedError


class sessionmaker(sessionmaker_):
    def __init__(self, *args, **kwargs):
        if "class_" not in kwargs:
            kwargs["class_"] = Session
        super().__init__(*args, **kwargs)


_Session: sessionmaker = None
_session: ContextVar[Optional[Session]] = ContextVar("_session", default=None)


class RepositoryMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app: ASGIApp,
        db_url: Optional[Union[str, URL]] = None,
        custom_engine: Optional[Engine] = None,
        engine_args: Dict = None,
        session_args: Dict = None,
        commit_on_exit: bool = False,
        sql_log: bool = False,
        slow_ms: float = 0,
    ):
        """
        :param app:           ASGI app
        :param db_url:        数据库连接字符串
        :param custom_engine: 自定义 Engine，与 db_url 二选一
        :param engine_args:   传给 create_engine 的额外参数
        :param session_args:  传给 sessionmaker 的额外参数
        :param commit_on_exit: 退出时是否自动提交
        :param sql_log:       是否打印 SQL 执行日志（语句 + 耗时）
        :param slow_ms:       慢查询阈值（毫秒），超过则以 WARNING 级别记录；0 表示不区分，全部 DEBUG
        """
        super().__init__(app)
        global _Session
        engine_args = engine_args or {}
        self.commit_on_exit = commit_on_exit
        session_args = session_args or {}
        if not custom_engine and not db_url:
            raise ValueError("You need to pass a db_url or a custom_engine parameter.")
        if not custom_engine:
            engine = create_engine(db_url, **engine_args)
        else:
            engine = custom_engine
        _Session = sessionmaker(bind=engine, **session_args)

        if sql_log:

            @event.listens_for(engine, "before_cursor_execute")
            def _before(conn, cursor, statement, parameters, context, executemany):
                conn.info.setdefault("_sql_start", []).append(time.perf_counter())
                logger.debug(f"[SQL] {statement.strip()} | params={parameters}")

            @event.listens_for(engine, "after_cursor_execute")
            def _after(conn, cursor, statement, parameters, context, executemany):
                elapsed = (time.perf_counter() - conn.info["_sql_start"].pop()) * 1000
                if slow_ms > 0 and elapsed >= slow_ms:
                    logger.warning(f"[SQL SLOW] {elapsed:.2f}ms")
                else:
                    logger.debug(f"[SQL] {elapsed:.2f}ms")

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint):
        with db(commit_on_exit=self.commit_on_exit):
            response = await call_next(request)
        return response


class DBSessionMeta(type):
    # using this metaclass means that we can access db.session as a property
    # at a class level,
    # rather than db().session

    @property
    def session(self) -> Session:
        if _Session is None:
            raise SessionNotInitialisedError
        session = _session.get()
        if session is None:
            raise MissingSessionError
        return session


class DBSession(metaclass=DBSessionMeta):
    def __init__(self, session_args: Dict = None, commit_on_exit: bool = False):
        self.token = None
        self.session_args = session_args or {}
        self.commit_on_exit = commit_on_exit

    def __enter__(self):
        if not isinstance(_Session, sessionmaker):
            raise SessionNotInitialisedError
        self.token = _session.set(_Session(**self.session_args))
        return type(self)

    def __exit__(self, exc_type, *_):
        sess = _session.get()
        if exc_type is not None:
            sess.rollback()
        if self.commit_on_exit:
            sess.commit()
        sess.close()
        _session.reset(self.token)


db: DBSessionMeta = DBSession
