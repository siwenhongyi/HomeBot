# encoding=utf-8
import json
import multiprocessing
import os
import random
import time
import traceback
from settings import BankConfig, BASE_DIR

from black_swan import Bot

MY_UID_LIST = []
bot_dict = {}


def get_bot(uid, **kwargs) -> Bot:
    res = bot_dict.get(uid, None)
    if res is None:
        res = Bot(uid=uid, **kwargs)
        bot_dict[uid] = res
    return res


def dig_and_do_bot_run(uid):
    def get_got_type(user, gb_balance, yb_balance, default_type=True):
        """
        :param bool default_type:
        :param Bot user:
        :param int gb_balance:
        :param int yb_balance:
        :return: dig got type
        :rtype: [bool, None]
        """
        # if user.uid == user.self_uid and gb_balance > 5e8 and yb_balance > 5e8:
        #     return None
        got_upper = BankConfig.get(user.uid, 0)
        if all((
            gb_balance <= 0 or gb_balance >= got_upper,
            yb_balance <= 0 or yb_balance >= got_upper,
        )):
            return None
        if gb_balance <= 0 or yb_balance <= 0:
            return gb_balance <= 0
        if gb_balance > 1.8e9 and yb_balance > got_upper:
            return default_type
        if gb_balance > 1.8e9 or yb_balance > got_upper:
            return gb_balance > got_upper
        return default_type
    time.sleep(random.randint(0, 10))
    print('%s 开始' % uid)
    bank_list = [
        35806354,
        35806557,
        35806558,
    ]
    b = get_bot(uid)
    while True:
        try:
            first_yb, first_gb = b.get_money_status(status_type=None)
            pre_yb, pre_gb = first_yb, first_gb
            got_yb = get_got_type(b, pre_gb, pre_yb, True)
            while got_yb is not None:
                got_yb = get_got_type(b, pre_gb, pre_yb, default_type=not got_yb)
                any_balance = b.dig_for_gold(is_gz=got_yb, max_dig=100)
                if any_balance >= int(1.5e9):
                    pay(
                        receive_money_uid=random.choice(bank_list),
                        pay_uid=b.uid,
                        pay_number=int(1e8),
                        pay_type=int(got_yb),
                        auto=False,
                    )
                if got_yb:
                    got_name = '元宝'
                    got_number = any_balance - first_yb
                    got_res = '挣了' if got_number >= 0 else '亏了'
                    b.log('%s%s%s', got_name, got_res, abs(got_number), say=True)
                    got_number = any_balance - pre_yb
                else:
                    got_name = '金币'
                    got_number = any_balance - first_gb
                    got_res = '挣了' if got_number >= 0 else '亏了'
                    b.log('%s%s%s', got_name, got_res, abs(got_number), say=True)
                    got_number = any_balance - pre_gb
                got_res = '挣了' if got_number >= 0 else '亏了'
                b.log(
                    '%s%s%d 余额%d',
                    got_name, got_res, abs(got_number), any_balance,
                    force_print=True,
                )
                pre_yb = any_balance if got_yb else pre_yb
                pre_gb = any_balance if not got_yb else pre_gb
            if b.uid != b.self_uid:
                break
            b.run()
        except AttributeError as e:
            b.log('疑似网络问题 即将重启 异常为%s', e, force_print=True)
        except Exception as e:
            info = traceback.format_exc()
            b.log('异常是%s 堆栈是 %s', e, info, say=True, force_print=True)
            b.log('重启', say=True, force_print=True)
    print('%s 结束' % b.uid)


def rob_car(uid, **kwargs):
    b = get_bot(uid, **kwargs)
    b.rob_car()


def pay(
    receive_money_uid=None,
    pay_uid=None,
    pay_number=None,
    pay_type=None,
    detail=None,
    auto=False,
):
    if receive_money_uid is None:
        receive_money_uid = int(input('请输入收款人uid'))
    if pay_uid is None:
        pay_uid = input('请输入付款人uid, 默认为尾号119的uid')
        pay_uid = int(pay_uid) if pay_uid else 35806119
    if pay_number is None:
        pay_number = int(eval(input('请输入支付金额')))
    if pay_type is None:
        pay_type = int(input('请输入支付类型 0-GB 1-元宝'))
    if detail is None:
        detail = ''
    b = get_bot(uid=pay_uid)
    if receive_money_uid == pay_uid:
        b.log('收款人和付款人不能相同', force_print=True)
        return
    b.log('支付密码验证状态 %s', b.payment_password_verified)
    if receive_money_uid in MY_UID_LIST and pay_uid in MY_UID_LIST and int(pay_type) == 1:
        receive_money_uid = b.self_uid
    pay_name = '元宝' if pay_type else '金币'
    if receive_money_uid in MY_UID_LIST:
        receive_b = get_bot(uid=receive_money_uid)
        balance, _ = receive_b.get_money_status(pay_type)
        if balance >= 1.8e9:
            b.log('收款人余额已达上限', force_print=True)
            return
    pay_res = True
    pay_count = 1
    while pay_number > 0 and pay_res:
        once_pay_number = min(pay_number, int(1e7))
        b.log('第%d次支付%d%s', pay_count, once_pay_number, pay_name, force_print=True)
        pay_res = b.pay_money(once_pay_number, pay_type, receive_money_uid, detail)
        if pay_res:
            pay_number -= once_pay_number
            pay_count += 1
            b.log('支付完成', force_print=True)
        else:
            b.log('支付失败', force_print=True)
    if auto:
        have_another_pay = input('是否继续支付？y/n')
        if have_another_pay == 'y':
            pay(auto=auto)
    return


# 通用批量请求
def batch_request(
        uid,
        path,
        data=None,
        params=None,
        method='POST',
        request_count=1,
):
    if data is None:
        data = {}
    if params is None:
        params = {}
    b = get_bot(uid=uid)
    send_count = 0
    while send_count < request_count:
        send_count += 1
        b.api_send_request(path, data=data, params=params, method=method)
        b.log('第%d次请求完成', send_count, force_print=True)


def jwt(uid):
    b = get_bot(uid=uid)
    while True:
        try:
            b.jw_tang()
            break
        except Exception as e:
            info = traceback.format_exc()
            b.log('异常是%s 堆栈是 %s', e, info, say=True, force_print=True)
            b.log('重启', say=True, force_print=True)


def do_task_by_option(option: [None, int], *args) -> None:
    if option is None:
        pay(auto=True)
        return
    option_func_dict = {
        0: rob_car,
        1: dig_and_do_bot_run,
        2: jwt,
    }
    global MY_UID_LIST
    if not MY_UID_LIST:
        const_json_path = os.path.join(BASE_DIR, 'config/const.json')
        with open(const_json_path, 'r') as f:
            MY_UID_LIST = json.load(f)['my_uid_list']
    target_uid_list = MY_UID_LIST if len(args) == 0 else [int(target_uid) for target_uid in args]
    p_count = len(target_uid_list)
    func = option_func_dict[option]
    p = multiprocessing.Pool(processes=p_count)
    for target_uid in target_uid_list:
        p.apply_async(func, args=(target_uid,))
    p.close()
    p.join()
    print('所有进程执行完毕 option=%s func=%s' % (option, func.__name__))
