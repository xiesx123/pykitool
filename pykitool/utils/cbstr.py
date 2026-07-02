from typing import Any

from hutool import ReUtil


# 是否为邮箱格式
def is_email(str: str) -> bool:
    EMAIL_PATTERN = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+.[a-zA-Z0-9-.]+$"
    return ReUtil.is_match(EMAIL_PATTERN, str)


# 生成终端超链接
def str_hyperlink(url: str, text: str) -> str:
    ESC = "\033"
    return f"{ESC}]8;;{url}{ESC}\\{text}{ESC}]8;;{ESC}\\"


# 字符填充
def pad_string(data: Any, length: int = 10, align: str = "right", char: str = " ") -> str:
    str_value = str(data)
    pad_len = length - len(str_value)
    if pad_len <= 0:
        return str_value
    padding = char * pad_len
    return str_value + padding if align == "left" else padding + str_value


# ================================ 调用示例 ================================

if __name__ == "__main__":

    # 是否为邮箱格式
    print(is_email("123@gamil.com"))
    print(is_email("123@qq.com"))

    # 生成终端超链接
    print(f"Hyperlink: {str_hyperlink('https://github.com', 'GitHub')}")

    # 字符填充
    print(pad_string(data="xxx", length=6, align="left", char="0"))
    print(pad_string(data="xxx", length=6, align="right", char="0"))
