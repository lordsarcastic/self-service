array = ['pea', 'pear', 'apple', 'for', 'april', 'apendix', 'peace', 1]


def longest_common_prefix(items: list[str | int]) -> list[str | int]:
    current_marker = 0
    prefixes = {}

    while True:
        
