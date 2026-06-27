# import os
# import sys

# sys.path.insert(0, os.getcwd())

# import sqlmodel
# import uvicorn
# from fastapi import FastAPI
# from fastapi_profiler import Profiler
# from fastapi_profiler.instrumentations import SQLAlchemyInstrumentation
# from sqlmodel import Field
# from sqlmodel_plus import SQLModelPlus
# from sqlmodel_repo import SQLModelRepo
# from src.db.middleware import DBSessionMiddleware, SQLModelPlus, db


# class Hero(SQLModelPlus, table=True):
#     __tablename__ = "test"
#     id: int | None = Field(default=None, primary_key=True)
#     name: str
#     age: int | None = None


# # 数据库
# engine = sqlmodel.create_engine("sqlite:///database.db", echo=True)

# # 应用
# app = FastAPI()

# # 中间件
# # 持久层
# app.add_middleware(DBSessionMiddleware, custom_engine=engine)
# # 持久层
# SQLModelPlus.set_engine(engine)

# # 性能分析
# Profiler(app, enabled=True)
# SQLAlchemyInstrumentation.instrument(engine)


# @app.get("/", include_in_schema=False)
# def hero():
#     # 方法一：使用 db.session 直接查询
#     users = db.session.exec(sqlmodel.select(Hero)).all()
#     assert len(users) == 1

#     # 方法二：使用 Hero 模型自带的 Session（可能是你自定义的类属性）
#     users = Hero.Session.exec(Hero.select).all()
#     assert len(users) == 1

#     # 方法三：使用封装好的仓储类 SQLModelRepo
#     repo = SQLModelRepo(model=Hero, db_engine=Hero.get_engine())
#     users = repo.all()
#     assert len(users) == 1
#     return users


# if __name__ == "__main__":
#     uvicorn.run(app)
