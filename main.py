# encoding=utf-8
import sys
from operator import do_task_by_option
MY_UID_LIST = []
bot_dict = {}


# todo option参数
if __name__ == '__main__':
    option = None
    if len(sys.argv) > 1:
        option = int(sys.argv[1])
    do_task_by_option(option, *sys.argv[2:])
