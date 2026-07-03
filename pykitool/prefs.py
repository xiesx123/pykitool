import os
import sys

sys.path.insert(0, os.getcwd())
from typing import Generic, Optional, Type, TypeVar

from loguru import logger
from pydantic import BaseModel

from pykitool.utils import cbfile, cbjson

T = TypeVar("T", bound=BaseModel)


class PrefsManager(Generic[T]):
    """
    泛型配置管理器，基于 Pydantic BaseModel 提供 JSON 文件持久化。

    示例示例：

        from pydantic import BaseModel
        from pykitool.prefs import PrefsManager

        class AppSetting(BaseModel):
            debug: bool = False
            name: str = "MyApp"

        _manager = PrefsManager(AppSetting, "config/settings.json")

        def get() -> AppSetting:
            return _manager.get()

        def save():
            _manager.save()

        def reload() -> AppSetting:
            return _manager.reload()
    """

    def __init__(self, model_class: Type[T], path: str) -> None:
        self._model_class = model_class
        self._path = path
        self._instance: Optional[T] = None
        self._loaded: bool = False

    # 从 JSON 文件加载配置，加载后将完整配置（含新增字段默认值）回写文件，确保 JSON 始终是最新结构
    def _load(self) -> None:
        try:
            content = cbfile.read(self._path)
            if cbjson.is_json(content):
                parsed = cbjson.load_json(content)
                if parsed:
                    self._instance = self._model_class.model_validate_json(json_data=content)
                    # 将完整配置回写，补全 JSON 中缺失的新字段
                    cbfile.write(self._path, self._instance.model_dump_json(indent=4))
                    logger.debug(f"prefs loaded and synced to {self._path}")
                    return
            # JSON 空或无效，则保存默认配置
            self.save()
        except (IOError, ValueError) as e:
            logger.error(f"Error: {str(e)}")
            self.save()

    # 保存当前配置到文件
    def save(self) -> None:
        try:
            if self._instance is None:
                self._instance = self._model_class()
            cbfile.write(self._path, self._instance.model_dump_json(indent=4))
            self._loaded = True
        except IOError as e:
            logger.error(f"Error: {str(e)}")

    # 获取配置实例（懒加载）
    def get(self) -> T:
        if self._instance is None:
            self._instance = self._model_class()
        if not self._loaded:
            self._load()
            self._loaded = True
        return self._instance

    # 手动刷新内存实例
    def reload(self) -> T:
        self._load()
        self._loaded = True
        logger.debug(f"prefs reloaded from {self._path}")
        return self._instance
