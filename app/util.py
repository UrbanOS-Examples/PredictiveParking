def log_exception(details):
  print("Backing off {wait:0.1f} seconds afters {tries} tries "
          "calling function {target} with args {args} and kwargs "
          "{kwargs}".format(**details))