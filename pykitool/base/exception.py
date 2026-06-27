# 异常基类
class RuntimeException(Exception):
    def __init__(self, message: str, code: int = -1):
        self.status_code = code
        self.message = message
        super().__init__(self.message)
