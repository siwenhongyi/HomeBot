# encoding=utf-8
import sys
from game_operator import do_task_by_option
MY_UID_LIST = []
bot_dict = {}


# todo option参数
if __name__ == '__main__':
    option = None
    if len(sys.argv) > 1:
        option = int(sys.argv[1]) if int(sys.argv[1]) >= 0 else None
    if option is None:
        option = input('please input option')
        option = int(option) if option.isdigit() and int(option) >= 0 else None
    do_task_by_option(option, *sys.argv[2:])
