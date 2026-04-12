def safe_divide(numerator, denominator, default=0):
    """
    Division safe from zero division.
    """
    try:
        return numerator / denominator
    except ZeroDivisionError:
        return default


def format_percentage(value, decimals=2):
    return round(value * 100, decimals)
