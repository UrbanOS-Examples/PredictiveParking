import sys


def log_exception(details):
    print("Backing off {wait:0.1f} seconds afters {tries} tries "
          "calling function {target} with args {args} and kwargs "
          "{kwargs}".format(**details))
    print(f"Backing off due to exception {sys.exc_info()}")


def snake_to_camel(snake):
    words = snake.split('_')
    return f'{words[0]}{"".join(word.title() for word in words[1:])}'
