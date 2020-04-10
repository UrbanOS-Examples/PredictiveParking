# This module handles the edge cases where parking can be paid for before parking opens up to a half hour in advance

def adjust(now):
    today8am = now.replace(hour=8, minute=0, second=0, microsecond=0)
    today730am = today8am.replace(hour=7, minute=30)
    today10pm = now.replace(hour=22, minute=0, second=0, microsecond=0)
    today1030pm = today10pm.replace(minute=30)

    if today730am <= now < today8am:
        return today8am
    elif today10pm < now <= today1030pm:
        return today10pm
    else:
        return now