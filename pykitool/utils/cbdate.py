# 将 cron 表达式的小时字段从 CST（东八区）转换为 UTC（-8h），仅处理固定数字小时
def cst_to_utc(expr: str) -> str:
    parts = expr.strip().split()
    if len(parts) != 5:
        return expr
    minute, hour, day, month, weekday = parts
    if hour.isdigit():
        utc_hour = (int(hour) - 8) % 24
        return " ".join([minute, str(utc_hour), day, month, weekday])
    return expr


# 将 cron 表达式的小时字段从 UTC 转换为 CST（东八区 +8h），仅处理固定数字小时
def utc_to_cst(expr: str) -> str:
    parts = expr.strip().split()
    if len(parts) != 5:
        return expr
    minute, hour, day, month, weekday = parts
    if hour.isdigit():
        cst_hour = (int(hour) + 8) % 24
        return " ".join([minute, str(cst_hour), day, month, weekday])
    return expr


# ================================ 调用示例 ================================

if __name__ == "__main__":

    expr = "0 8 * * *"
    print(cst_to_utc(expr))

    expr = "0 0 * * *"
    print(utc_to_cst(expr))
