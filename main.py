# encoding=utf-8
import json
import os
import queue
import random
import re
import sys
import math
import atexit
import time
import traceback
from datetime import datetime
from types import FunctionType

import bs4
import requests

from tools import get_res, get_system_message

BASE_URL = 'http://3gqq.cn/'
IS_MAC = sys.platform == 'darwin'


class Bot:
    class Node:
        def __init__(self, ts, func, kwargs=None):
            self.time = ts
            self.func = func
            self.kwargs = kwargs

        def __lt__(self, other):
            return self.time < other.time

    def __init__(self):
        self.save_type_mapping = {
            0: 'GB',
            1: '元宝',
        }
        self.save_type_upper_number = {
            'GB': 3e8,
            '元宝': 2e5,
        }
        self.save_money_data = {
            0: [
                # 35805993, # 飞花
                35806354,   # 小号
            ],
            1: [
                # 35803370, # 大哥
                35806354,   # 小号
            ],
        }
        # 注册析构函数
        atexit.register(self.del_func)
        # 存储 每个任务开始时间 使用的函数 [time, func, kwargs]
        self.box_total_revenue = dict()
        self.save_money = dict()
        self.lazy_start = 1
        self.interval = 20 * 60
        self.uid_update_time = int(time.time())
        self.d = datetime.today().day
        self.q = queue.PriorityQueue()
        self.session = requests.Session()
        self.uid = 35806119
        self.log_file = open('log.log', mode='a')
        self.all_uid_list = []
        self.farm_black_list = []
        self.garden_black_list = []
        self.done_uid = dict()
        self.const_blank_list = [
            35795908,
            35800386,
        ]

    def del_func(self):
        self.log('======del======')
        self.save_data()
        self.log_file.close()

    def log(self, msg, *args, **kwargs):
        if '%' in msg:
            msg = msg % args
        if kwargs.get('print_time', False):
            msg = '时间|' + datetime.now().strftime('%H:%M:%S') + '| ' + msg
        if kwargs.get('print', True):
            print(msg)
        if kwargs.get('say', False) and IS_MAC:
            os.system('say ' + msg)
        self.log_file.write(msg + '\n')
        self.log_file.flush()

    def _send_request(self, url, data=None, params=None, method='get', need_sleep=True):
        if need_sleep:
            time.sleep(0.5)
        else:
            time.sleep(0.1)
        if 'login' in url:
            time.sleep(2)
        try:
            if method == 'get':
                resp = self.session.get(url, params=params, data=data)
            else:
                resp = self.session.post(url, data=data)
        except ConnectionResetError as err:
            self.log('连接异常 异常=%s，url=%s 参数为', err, url, locals())
            return self._send_request(url, data, params, method, need_sleep)

        if resp.status_code != 200:
            self.log('got error status code=%s from url=%s', resp.status_code, resp.url)
        if resp.text.find('家园社区密码') != -1:
            self.login()
            return self._send_request(url, data=data, params=params, method=method)

        resp.encoding = 'utf-8'
        return resp

    def checkout_login(func):
        def wrapper(self, *args, **kwargs):
            if self.session.cookies.get('uid') is None:
                try:
                    with open('cookies.json', mode='r') as f:
                        cookies = f.read()
                        cookies = json.loads(cookies)
                        for k, v in cookies.items():
                            self.session.cookies.set(k, v)
                except Exception as err:
                    self.log('%s', err)
                    pass
            check_login_resp = self._send_request(BASE_URL + 'home/my_home.html')
            if any((
                    check_login_resp.status_code != 200,
                    check_login_resp.url.find('login/login.html') != -1,
                    check_login_resp.text.find('家园社区密码：') != -1,
            )):
                self.log('需要登录')
                self.login()
            self.log('时间 %s 开始函数 %s', int(time.time()), func.__name__)
            return func(self, *args, **kwargs)

        return wrapper

    def save_data(self):
        """
        保存数据
        :return: None
        """
        with open('friends.json', 'w') as f:
            f.write(json.dumps(
                {
                    'all_uid': list(set(self.all_uid_list)),
                    'farm_black_list': list(set(self.farm_black_list)),
                    'garden_black_list': list(set(self.garden_black_list)),
                    'uid_update_time': self.uid_update_time,
                    'done_uid': self.done_uid,
                    'lazy_start': self.lazy_start,
                },
                indent=4,
            ))
        with open('dig_data.json', 'w') as f:
            f.write(json.dumps(
                {
                    'box_total_revenue': self.box_total_revenue,
                    'save_money': self.save_money,
                },
                indent=4,
                ensure_ascii=False,
            ))

    def once_init(self):
        # 获取今天的日期
        today = datetime.today()
        self.d = today.day
        # 获取所有uid
        curr_time = int(time.time())
        with open('friends.json', mode='r') as f:
            uid_dict = json.loads(f.read())
            self.all_uid_list = uid_dict.get('all_uid', [])
            self.farm_black_list = uid_dict.get('farm_black_list', [])
            self.garden_black_list = uid_dict.get('garden_black_list', [])
            self.uid_update_time = uid_dict.get('update_time', curr_time)
            self.lazy_start = uid_dict.get('lazy_start', 1)
            if len(self.all_uid_list) == 0:
                self.lazy_start = 1
        # 加入固定黑名单
        self.garden_black_list.extend(self.const_blank_list)
        self.farm_black_list.extend(self.const_blank_list)
        # 初始化任务队列
        # 许愿 签到 花园签到
        self.q.put(self.Node(curr_time - 4, self.xy_everyday, {'xy_count': 0}))
        self.q.put(self.Node(curr_time - 4, self.qd_every_day, {}))
        self.q.put(self.Node(curr_time - 4, self.qd_garden, {}))
        # 收菜 收花 偷农场 偷花园
        self.q.put(self.Node(curr_time - 1, self.self_farm, {}))
        self.q.put(self.Node(curr_time - 2, self.self_garden, {}))
        self.q.put(self.Node(curr_time + 0, self.friends_garden, {}))
        self.q.put(self.Node(curr_time + 1, self.friends_farm, {}))

    def dig_init(self):
        with open('dig_data.json', mode='r+') as f:
            dig_data = json.loads(f.read())
            self.box_total_revenue = dig_data.get('box_total_revenue', {})
            self.save_money = dig_data.get('save_money', {})
            for save_type in self.save_type_mapping.values():
                if save_type not in self.save_money:
                    self.save_money[save_type] = {}
            if '交易号' not in self.save_money:
                self.save_money['交易号'] = []
        for i in range(1, 17):
            if str(i) not in self.box_total_revenue:
                self.box_total_revenue[str(i)] = 0
        self.q.put(self.Node(int(time.time()), self.dig_for_gold, {'is_gz': self.lazy_start % 5 != 0}))

    def login(self, VerCode=None):
        login_path = 'login/login.html'
        form_data = {
            'act': 'ok',
            'name': self.uid,
            'pass': '1587142699a'
        }
        if VerCode:
            time.sleep(0.1)
            form_data['VerCode'] = VerCode
        login_resp = self._send_request(BASE_URL + login_path, data=form_data, method='post')
        if login_resp.status_code != 200:
            self.log('登录失败')
            time.sleep(0.1)
            return self.login()
        if login_resp.text.find('登录成功') != -1:
            self.log('登录成功')
            save_data = self.session.cookies.get_dict()
            with open('cookies.json', 'w') as f:
                json.dump(save_data, f)
            return True
        if login_resp.text.find('alt="验证码"') != -1:
            soup = bs4.BeautifulSoup(login_resp.text, 'html.parser')
            img_url = soup.select_one('body > img')['src'][1:]
            with open('captcha.png', 'wb') as f:
                var_code_img = self._send_request(BASE_URL + img_url)
                f.write(var_code_img.content)
                f.close()
            VerCode = get_res('captcha.png')
            return self.login(VerCode)
        if login_resp.text.find('密码错误') != -1:
            self.log('密码错误')
            return False
        return True

    @checkout_login
    def farm_friends_init(self, update=False, start_page=1, end_page=10):
        """
        初始化
        :return: list of all uid
        :rtype list
        """
        if update:
            return []
        farm_level_path = r'/game/farm/level-{}.html'
        re_string = r'<a href="/game/farm/farm/(\d*)\.html"'
        friends_uid = []
        for i in range(start_page, end_page + 1):
            rel_path = farm_level_path.format(i)
            resp = self._send_request(BASE_URL + rel_path, need_sleep=False)
            farm_level_compile = re.compile(re_string)
            uid_list = re.findall(farm_level_compile, resp.text)
            for uid in uid_list:
                uid = int(uid)
                friends_uid.append(uid)

        return friends_uid

    @checkout_login
    def garden_friends_init(self, start_index=1, end_index=None, update=False):
        """
        初始化
        :return: list of all uid
        :rtype list
        """
        garden_path = r'game/garden/user/hy_qd.html'
        page_size = end_index if end_index else 35 if update else 3500
        re_string = r'<a href="/home/profile/(\d+).html"'
        garden_compile = re.compile(re_string)
        res = set()
        curr_time = int(time.time())
        for i in range(start_index, page_size + 1):
            resp = self._send_request(BASE_URL + garden_path, params={'page': i}, need_sleep=False)
            uid_list = re.findall(garden_compile, resp.text)
            for uid in uid_list:
                uid = int(uid)
                # self.log('添加uid %d', uid)
                res.add(uid)
                self.q.put(self.Node(curr_time, self.steal_flower, {'friend_uid': uid}))
                self.q.put(self.Node(curr_time, self.steal_vegetables, {'friend_uid': uid}))
        return list(res)

    @checkout_login
    def xy_everyday(self, **kwargs):
        xy_path = 'home/xy_add_ok.html'
        xy_count = kwargs.get('xy_count', 1)
        data = {
            'content': '2022希望3GQQ家园社区的所有朋友幸福美满！每天开心！'
        }
        xy_resp = self._send_request(BASE_URL + xy_path, data=data, method='post')
        if xy_resp.status_code != 200 or xy_resp.text.find('今天许愿已经达到上限啦。请明天再来') != -1:
            self.log('今天许愿已经达到上限啦。请明天再来')
            xy_count = 2
        curr_time = int(time.time())
        if xy_count == 2:
            tomorrow = curr_time + 24 * 3600
            self.log('今天许愿2次 完成')
            self.q.put(self.Node(tomorrow, self.xy_everyday, {'xy_count': 1}))
        else:
            self.q.put(self.Node(curr_time + 1800, self.xy_everyday, {'xy_count': xy_count + 1}))

    @checkout_login
    def qd_every_day(self, **kwargs):
        qd_path = 'home/7t.html'
        qd_resp = self._send_request(BASE_URL + qd_path)
        if qd_resp.status_code != 200 or qd_resp.text.find('今天的已经领完啦') != -1:
            self.log('今天的已经签到过了')
        else:
            system_msg = get_system_message(qd_resp.content)
            if len(system_msg) == 1:
                system_msg = system_msg[0]
            self.log('签到成功 %s', system_msg)
        tomorrow = int(time.time()) + 24 * 3600
        self.q.put(self.Node(tomorrow, self.qd_every_day, {}))

    @checkout_login
    def steal_vegetables(self, **kwargs):
        friend_uid = kwargs.get('friend_uid')
        page_size = 1
        page_index = 1
        steal_vegetables_path = r'game/farm/farm/%d/{}.html' % friend_uid
        steal_bank_res_list = [
            '本农场禁止摘取',
            '本农场只有好友才可以摘取！',
        ]
        curr_time = int(time.time())
        can_steal = True
        done = False
        while page_index <= page_size and not done:
            real_path = steal_vegetables_path.format(page_index)
            resp = self._send_request(BASE_URL + real_path)
            if resp.url.find('farm_not') != -1:
                return False
            soup = bs4.BeautifulSoup(resp.text.replace('\n', '').replace('\r', ''), 'html.parser')
            vegetables = soup.select('body > div.list')[0]
            if page_size == 1:
                text = soup.select('body > div.list')[0].text.replace('\n', '').replace('\r', '')
                page_size_compile = re.compile(r'\(第1/(\d*)页/共(\d*)条记录\)')
                page_size_list = re.findall(page_size_compile, text)
                page_size = int(page_size_list[0][0])
            vegetable_desc_compile = re.compile(r'(.*)/(\d+)分钟后(.*)')
            for vegetable in vegetables.children:
                # 获取作物描述
                vegetable_desc = vegetable.text.replace('\n', '').replace('\r', '')
                vegetable_desc_list = re.findall(vegetable_desc_compile, vegetable_desc)
                if len(vegetable_desc_list) > 0:
                    for desc_item in vegetable_desc_list:
                        need_min = int(desc_item[1])
                        next_time = curr_time + need_min * 60
                        self.q.put(self.Node(next_time, self.steal_vegetables, {'friend_uid': friend_uid}))
                # 获取所有a 标签
                a_list = vegetable.select('a')
                length = len(a_list)
                if length == 0:
                    done = True
                    break
                vegetable_name = a_list[0].text
                if vegetable_name in ['下页', '上页']:
                    break
                for i in range(0, length):
                    operator_name = a_list[i].text
                    if operator_name in ['收获', '除虫', '除草', '浇水', '偷菜']:
                        if not can_steal and operator_name == '偷菜':
                            continue
                        operator_path = a_list[i].attrs['href'][1:]
                        steal_resp = self._send_request(BASE_URL + operator_path)
                        content = steal_resp.text.replace('\n', '').replace('\r', '')
                        res = get_system_message(content)
                        self.log('在%s 对作物%s 操作%s 结果 %s', friend_uid, vegetable_name, operator_name, res)
                        if operator_name == '偷菜' and any((content.find(k) != -1 for k in steal_bank_res_list)):
                            can_steal = False
            page_index += 1
            if done:
                break
        self.done_uid[friend_uid] = curr_time
        return True

    @checkout_login
    def self_farm(self, **kwargs):
        self.log('开始打理自己的农场')
        base_path = 'game/farm/{}.html'
        operator_name = ['收获', '翻地', '种植', '浇水', '除草', '除虫']
        path_list = ['pick', 'plow', 'plant', 'drys', 'weed', 'pest']
        for path in path_list:
            rel_path = base_path.format(path)
            resp = self._send_request(BASE_URL + rel_path)
            system_message = get_system_message(resp.content)
            self.log('在自己的农场操作%s 结果 %s', operator_name[path_list.index(path)], system_message)
            if path == 'plant':
                content = resp.text.replace('\n', '').replace('\r', '')
                soup = bs4.BeautifulSoup(content, 'html.parser')
                a_list = soup.select('body')[0].select('a')
                for a in a_list:
                    if a.text != '选择种植':
                        continue
                    plant_path = a.attrs['href'][1:]
                    self._send_request(BASE_URL + plant_path)
        # save next time
        my_farm_path = 'game/farm/my_farm.html'
        resp = self._send_request(BASE_URL + my_farm_path)
        content = resp.text.replace('\n', '').replace('\r', '')
        soup = bs4.BeautifulSoup(content, 'html.parser')
        # 获取所有蔬菜标签
        vegetables = soup.select('body > div.list')[0]
        curr_time = int(time.time())
        next_time_compile = re.compile(r'/((\d*)小时)*(\d*)分钟后')
        for vegetable in vegetables.children:
            text = vegetable.text
            if text.find('土地') == -1:
                break
            _, next_time_hour, next_time_min = re.findall(next_time_compile, text)[0]
            next_time_hour = int(next_time_hour) if next_time_hour != '' else 0
            next_time_min = int(next_time_min)
            next_time = next_time_hour * 3600 + next_time_min * 60 + curr_time
            self.q.put(self.Node(next_time, self.self_farm, {}))
        return True

    def friends_farm(self, **kwargs):
        curr_time = int(time.time())
        for uid in self.all_uid_list:
            self.save_data()
            if uid in self.farm_black_list:
                continue
            last_operate_time = self.done_uid.get(uid, 0)
            if curr_time - last_operate_time < self.interval:
                self.q.put(self.Node(last_operate_time + self.interval, self.steal_vegetables, {'friend_uid': uid}))
                self.log('农场%d操作过于频繁, %d秒后再操作', uid, curr_time - last_operate_time)
                continue
            open_farm = self.steal_vegetables(friend_uid=uid)
            self.done_uid[uid] = curr_time
            if not open_farm:
                self.farm_black_list.append(uid)

    @checkout_login
    def qd_garden(self, **kwargs):
        qd_path = 'game/garden/user/hy_qd.html'
        qd_resp = self._send_request(BASE_URL + qd_path)
        if qd_resp.status_code != 200 or qd_resp.text.find('你今天领取过了，明天记得来领取独特的种子') != -1:
            self.log('花园签到 今天的已经签到过了')
        tomorrow = int(time.time()) + 24 * 3600
        self.q.put(self.Node(tomorrow, self.qd_garden, {}))

    @checkout_login
    def steal_flower(self, **kwargs):
        friend_uid = kwargs.get('friend_uid')
        steal_flower_path = 'game/garden/garden.html'
        params = {'gid': friend_uid}
        # 收获花
        resp = self._send_request(BASE_URL + steal_flower_path, params=params)
        if resp.status_code != 200 or resp.text.find('对方没有开通花园') != -1:
            self.garden_black_list.append(friend_uid)
            self.log('没有开通花园 %s', friend_uid)
            self.q.put(self.Node(int(time.time()) + 10, self.save_data, {}))
            return False
        # 获取下次来操作的时间
        content = resp.text.replace('\n', '').replace('\r', '')
        soup = bs4.BeautifulSoup(content, 'html.parser')
        all_text = soup.select('body')[0].text
        next_time_compile = re.compile(r'(\d*)分钟后开花')
        next_time_list = re.findall(next_time_compile, all_text)
        curr_time = int(time.time())
        for next_time_min in next_time_list:
            m = int(next_time_min)
            self.log('%s 在%s 分钟后操作', friend_uid, m)
            next_time = curr_time + m * 60
            self.q.put(self.Node(next_time, self.steal_flower, {'friend_uid': friend_uid}))
        # 操作列表 浇水.锄草.捉虫.偷菜
        operator_name_list = ['浇水', '锄草', '捉虫', '偷菜']
        operator_list = ['watera', 'weeda', 'pesta', 'gathera']
        operator_path = 'game/garden/{}/{}.html'
        for operator in operator_list:
            real_path = operator_path.format(operator, friend_uid)
            operator_resp = self._send_request(BASE_URL + real_path)
            operator_msg = get_system_message(operator_resp.content)
            if operator == 'gathera' and len(operator_msg) == 0:
                content = operator_resp.text.replace('\n', '').replace('\r', '')
                soup = bs4.BeautifulSoup(content, 'html.parser')
                gathera_res = soup.select('body > div.list')[0]
                for gather_res in gathera_res.children:
                    operator_msg.append(gather_res.text)
            self.log('%d 花园 操作%s 结果%s', friend_uid, operator_name_list[operator_list.index(operator)], operator_msg)
        return True

    def friends_garden(self, **kwargs):
        curr_time = int(time.time())
        for uid in self.all_uid_list:
            self.save_data()
            if uid in self.garden_black_list:
                continue
            last_operate_time = self.done_uid.get(uid, 0)
            if curr_time - last_operate_time < self.interval:
                self.q.put(self.Node(last_operate_time + self.interval, self.steal_vegetables, {'friend_uid': uid}))
                self.log('花园%d操作过于频繁, %d秒后再操作', uid, curr_time - last_operate_time)
                continue
            open_garden = self.steal_flower(friend_uid=uid)
            self.done_uid[uid] = curr_time
            if not open_garden:
                self.garden_black_list.append(uid)

    @checkout_login
    def self_garden(self, **kwargs):
        self.log('开始打理自己的花园')
        operator_mapping = {
            '浇水': 'watera',
            '锄草': 'weeda',
            '捉虫': 'pesta',
            '收获': 'gathera',
            '播种': 'sowing_list',
        }
        operators = []
        self_garden_path = 'game/garden/user/my_garden.html'
        operator_path = 'game/garden/user/{}.html'
        my_garden_resp = self._send_request(BASE_URL + self_garden_path)
        content = my_garden_resp.text.replace('\n', '').replace('\r', '')
        soup = bs4.BeautifulSoup(content, 'html.parser')
        a_list = soup.select('body > a')
        need_sowing = 0
        for a in a_list:
            if a.text in operator_mapping.keys():
                if a.text == '播种' or a.text == '收获':
                    need_sowing += 1
                if a.text != '播种':
                    operators.append((a.text, operator_mapping[a.text]))
        for operator_name, operator in operators:
            operator_resp = self._send_request(BASE_URL + operator_path.format(operator))
            operator_msg = get_system_message(operator_resp.content)
            self.log('自己的花园 操作%s 结果%s', operator_name, operator_msg)
        if need_sowing > 0:
            sowing_resp = self._send_request(BASE_URL + operator_path.format('sowing_list'))
            content = sowing_resp.text.replace('\n', '').replace('\r', '')
            soup = bs4.BeautifulSoup(content, 'html.parser')
            row_list = soup.select('body > div.list')[0]
            item_compile = re.compile(r'\d\.(.*) \((\d*)\)')
            for row in row_list.children:
                if row.text == '':
                    break
                item_list = re.findall(item_compile, row.text)
                item_name, item_count = item_list[0]
                item_count = int(item_count)
                sowing_item_path = row.select('a')[1]['href'][1:]
                sowing_item_resp = self._send_request(BASE_URL + sowing_item_path)
                sowing_item_msg = get_system_message(sowing_item_resp.content)
                self.log('自己的花园 播种%s 数量%d 结果%s', item_name, item_count, sowing_item_msg)
                need_sowing -= item_count
            # 播种 1 分钟后来 浇水
            curr_time = int(time.time())
            self.q.put(self.Node(curr_time + 60, self.self_garden, {}))

        return True

    # 激情挖宝
    @checkout_login
    def dig_for_gold(self, **kwargs):
        def get_status(status_type=False):
            status_type_map = {
                2500: 16,
                3500: 32,
                4500: 64,
                9000: 128,
                18000: 256,
                25000: 512,
            }
            my_gb = 'home/money/'
            my_gb_resp = self._send_request(BASE_URL + my_gb)
            text = my_gb_resp.text.replace('\n', '').replace('\r', '')
            if status_type:
                my_gb_compile = re.compile(r'元宝余额:(\d+)')
                a = int(my_gb_compile.search(text).group(1))
                if a <= 30000:
                    y = 8
                    for ky, vl in status_type_map.items():
                        if a >= ky:
                            y = vl
                    return a, y
            else:
                my_gb_compile = re.compile(r'GB余额:(\d+)')
                a = int(my_gb_compile.search(text).group(1))
            z = a // 20
            y = z - 1
            for bit_pos in [1, 2, 4, 8, 16]:
                y |= (y >> bit_pos)
            y += 1
            y = y if abs((y >> 1) - z) > abs(y - z) else y >> 1
            return a, y

        def get_box_id():
            return random.randint(1, 16)

        def save_money(save_balance, save_type=0, t_uid=35806354):
            save_balance = int(save_balance)
            # 获取已经存款数量
            save_type_name = self.save_type_mapping[save_type]
            change_data = self.save_money[save_type_name]
            if str(t_uid) in change_data:
                if change_data[str(t_uid)] >= self.save_type_upper_number[save_type_name]:
                    self.log('存款上限 放弃存款', say=True)
                    return
            else:
                change_data[str(t_uid)] = 0
            # 1 验证回复密码
            v_pass_path = 'home/money/vpass.html'
            save_money_path = 'home/money/trade_add.html'
            v_pass_params = {
                'srcurl': '/' + save_money_path,
            }
            form_data = {
                'act': 'ok',
                'vpass': 972520,
            }
            v_pass_resp = self._send_request(BASE_URL + v_pass_path, params=v_pass_params, data=form_data)
            if v_pass_resp.text.find('校验成功') == -1:
                self.log('验证支付密码失败')
                return False
            # 2 提交 支付
            form_data = {
                'act': 'ok',                  # 操作验证
                'type': 1,                    # 贸易类型 1 即时 2 担保
                'money': save_type,           # 转账货币类型 0 GB 1 元宝
                'amount': save_balance,       # 转账金额
                'detail': '',                 # 转账说明
                'tuid': t_uid,                # 转账目标
                'tmoney': '',                 # 索要货币类型
                'tamount': '',                # 索要货币数量
            }
            save_money_resp = self._send_request(BASE_URL + save_money_path, data=form_data, method='POST')
            # 确认支付
            save_money_content = save_money_resp.text.replace('\n', '').replace('\r', '').replace(' ', '')
            if save_money_content.find('确认提交') == -1:
                self.log('提交交易失败')
                return False
            t_id = int(re.search(r'type="hidden"name="tid"value="(\d+)"/>', save_money_content).group(1))
            form_data = {
                'act': 'ok',
                'tid': t_id,
            }
            # 3 提交确认
            save_money_resp = self._send_request(BASE_URL + save_money_path, data=form_data, method='POST')
            if save_money_resp.text.find('发布成功！') == -1:
                self.log('确认交易失败')
                return False
            self.log('存款成功 %s', save_balance, say=True)
            change_data[str(t_uid)] += save_balance
            self.save_money['交易号'].append(t_id)
            self.save_data()
            return True

        best_box_id = 0
        best_profit = 0
        for k, v in self.box_total_revenue.items():
            if v > best_profit:
                best_profit = v
                best_box_id = k
        self.log('%s箱子收益最好 %s', best_box_id, best_profit)
        is_gz = kwargs.get('is_gz', False)
        yb_balance, yb_interval = get_status(True)
        gb_balance, gb_interval = get_status(False)
        yb_max_got = 100
        only_gb = kwargs.get('only_gb', False)
        dedication_number = 15
        if yb_balance >= 1e8 and gb_balance >= 1e8:
            self.log('双超1亿yb %d gb %d 无视限制', yb_balance, gb_balance)
            dedication_number = yb_max_got = 1e8
            only_gb = True
        balance, interval = (yb_balance, yb_interval) if is_gz else (gb_balance, gb_interval)
        self.log('策略元组 元宝撤出数量 %d 只搞GB %s ', yb_max_got, only_gb)
        if balance < 100:
            self.log('余额不足 %s', balance, say=True)
            return balance
        if is_gz:
            if balance >= 6e4:
                self.log('尝试存款')
                save_money(10000, 1, random.choice(self.save_money_data[1]))
                balance, interval = get_status(is_gz)
        if not is_gz:
            if balance > 1e8:
                self.log('尝试存款')
                target_uid = random.choice(self.save_money_data[0])
                save_money(1e7, 0, t_uid=target_uid)
        self.log('开始财富 数量%d 押注上限 %d', balance, interval)
        play_path = '/game/diggingtreasure/play.aspx'
        if is_gz:
            play_path = play_path.replace('play', 'play2')
        box_number = kwargs.get('box_number') or get_box_id()
        params = {'num1': box_number}
        all_failed_count = 0
        fail_count = 0
        success_count = 0
        first_curr_number = 2
        curr_number = first_curr_number
        new_money = 0
        interval_count = 0
        curr_count = 0
        max_dig = kwargs.get('max_dig', 1000)
        fail_count_list = []
        nice_count = 0
        max_curr_count = 1 if balance >= 2e4 else 2 if balance >= 1e4 else 3
        i = 1
        while i <= max_dig:
            self.log('第%s次押注 %s', i, box_number)
            # if nice_count >= 15:
            #     self.log('距离上次黑天鹅太久 nice count %s', nice_count)
            black_swan_limit = int(math.log(interval, 2))
            if curr_count >= max_curr_count:
                curr_number = min(int(curr_number * 1.5), interval)
                curr_count = 0
            curr_count += 1
            if curr_number == interval:
                interval_count += 1
            else:
                interval_count = 0
            if interval_count > 5:
                self.log('error 激情挖宝 最高点 失败%d次', interval_count - 1)
            params['num'] = curr_number
            params['num1'] = box_number
            new_money -= curr_number
            resp = self._send_request(BASE_URL + play_path, params=params)
            content = resp.text.replace('\n', '').replace('\r', '')
            if content.find('眼前一片金光四射') != -1:
                if fail_count >= black_swan_limit:
                    nice_count = 0
                else:
                    nice_count += 1
                fail_count_list.append(fail_count)
                new_money += curr_number * 6
                # if new_money < 0 and new_money + interval * 2 < 0:
                #     self.log('dangerous 亏损超两上限 重新计算上限')
                #     _, interval = get_status(is_gz)
                all_failed_count += fail_count
                success_count += 1
                self.box_total_revenue[str(box_number)] += curr_number * 6
                self.save_data()
                self.log('激情挖宝 成功 成本%s 盈利 %s', curr_number, new_money)
                self.log('平均挖宝次数 %.2f 成功率%.2f', i / success_count, success_count / i)
                box_number = get_box_id()
                fail_count = 0
                curr_number = first_curr_number
                curr_count = 0
                if max_dig - i <= max(max(fail_count_list), 10):
                    self.log('剩余次数不足%d次 撤了', max(fail_count_list))
                    break
                if is_gz and new_money > yb_max_got:
                    self.log('元宝赚了 %d 撤出', new_money, print_time=True)
                    break
            else:
                self.log('激情挖宝 失败 成本%s', curr_number)
                fail_count += 1
                self.box_total_revenue[str(box_number)] -= curr_number
                if not is_gz and fail_count >= dedication_number and not only_gb:
                    self.log('激情挖宝 失败超过%d次 搞元宝 垫刀收益 %s', fail_count, new_money, print_time=True)
                    return self.dig_for_gold(is_gz=True, max_dig=100, box_number=box_number)
                if i == max_dig and balance + new_money > curr_number:
                    max_dig += 1
            i += 1
        got_type = '元宝' if is_gz else 'GB'
        new_balance, interval = get_status(is_gz)
        self.log(
            '激情挖宝 成功%d次 失败%d次 %s结算%d 最终财富%d',
            success_count,
            all_failed_count,
            got_type,
            new_money,
            new_balance,
            say=is_gz or new_money < -500000,
        )
        self.log(
            '失败列表%s',
            fail_count_list,
            print_time=True
        )
        self.save_data()
        return new_balance

    def run(self):
        task_index = 0
        while True:
            if self.d is None or self.q.empty():
                self.once_init()
                self.dig_init()
            while not self.q.empty():
                task = self.q.get()
                curr_time = int(time.time())
                if task_index % 2 == 0:
                    self.log('当前任务数量%s', task_index)
                if self.lazy_start % 2:
                    self.lazy_init(index=self.lazy_start)
                    self.lazy_start += 1
                if curr_time >= task.time:
                    self.log('开始任务')
                    task.func(**task.kwargs)
                    self.save_data()
                    task_index += 1
                else:
                    self.q.put(task)
                    wait_time = task.time - curr_time
                    self.log('sleep %d', wait_time)
                    if wait_time < 5:
                        time.sleep(wait_time)
                    else:
                        while curr_time < task.time:
                            self.lazy_init(index=self.lazy_start)
                            self.dig_for_gold(is_gz=self.lazy_start % 5 != 0)
                            self.lazy_start += 1
                            time.sleep(5)
                            curr_time = int(time.time())
                            self.log('sleep %d', task.time - curr_time)

    def lazy_init(self, index: int):
        # 在执行的过程中 逐步 加载uid
        old_length = len(self.all_uid_list)
        self.log('懒加载 用户长度%s', old_length)
        self.log('开始加载第%d个花园签到表 %d个农场排名表', index, index)
        res = [] if index > 10 else self.farm_friends_init(start_page=index, end_page=index)
        res.extend(self.garden_friends_init(start_index=index, end_index=index, update=True))
        self.all_uid_list.extend(res)
        self.all_uid_list = list(set(self.all_uid_list))
        self.log('加载第%d个花园签到表 %d个农场排名表 结束', index, index)
        if len(self.all_uid_list) > old_length:
            self.log('加载第%d个花园签到表 %d个农场排名表 加载了%d个用户', index, index, len(self.all_uid_list) - old_length)
            self.save_data()


if __name__ == '__main__':
    b = Bot()
    b.dig_init()
    play2 = 1
    traditional_operation = b.d % 5 == 0

    while True:
        try:
            got_yb = play2 % 5 != 0
            ogb = play2 % 3 == 0
            any_balance = b.dig_for_gold(is_gz=got_yb, max_dig=100, only_gb=not got_yb)
            play2 += 1
            if any_balance <= 8e8:
                continue
            if traditional_operation:
                b.run()
        except Exception as e:
            info = traceback.format_exc()
            b.log('异常是%s 堆栈是 %s', e, info)
            b.log('重启')
