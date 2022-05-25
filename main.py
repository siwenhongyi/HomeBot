# encoding=utf-8
import atexit
import json
import multiprocessing
import os
import queue
import random
import re
import sys
import time
import traceback
from datetime import datetime

import bs4
import requests

import tools

BASE_URL = 'http://3gqq.cn/'
IS_MAC = sys.platform == 'darwin'
MY_UID_LIST = [
    35806119,
    35806354,
]
p_count = 2
# 类实例列表
bot_dict = {}


class Bot:
    class Node:
        def __init__(self, ts, func, kwargs=None):
            self.time = ts
            self.func = func
            self.kwargs = kwargs
            self.name = self.func.__name__

        def __lt__(self, other):
            return self.time < other.time

    def __init__(self, uid=35806119, **kwargs):
        self.payment_password_verified = False
        # 注册析构函数
        atexit.register(self.del_func)
        # 存储 每个任务开始时间 使用的函数 [time, func, kwargs]
        self.lazy_start = 1
        self.interval = 30 * 60
        self.q = queue.PriorityQueue()
        self.session = requests.Session()
        self.uid = uid
        self.pid = os.getpid()
        self.uid_str = str(uid)[-3:]
        self.self_uid = 35806119
        self.password = kwargs.get('password', '1587142699a')
        self.v_pass = kwargs.get('v_pass', '972520')
        self.log_file = open('%s_log.log' % self.uid_str, mode='a')
        self.all_friends_list = []
        # 已经成功添加的好友
        self.friends_added = []
        # 黑名单
        self.friends_black_list = []
        self.all_uid_list = []
        self.farm_black_list = []
        self.gather_black_list = []
        self.garden_black_list = []
        self.garden_done_uid = dict()
        self.farm_done_uid = dict()
        self.const_blank_list = [
            35795908,
            35800386,
            35804236,
        ]
        self.log_count = 0
        self.config_init()
        self.session_init()

    def del_func(self):
        self.log('======del======')
        self.save_data()
        self.log_file.flush()
        self.log_file.close()

    def log(self, msg, *args, **kwargs):
        self.log_count += 1
        if '%' in msg:
            msg = msg % args
        dt = datetime.now()
        if kwargs.get('say', False) and IS_MAC and dt.hour >= 20:
            os.system('say "%s"' % msg)
        msg = '时间|' + dt.strftime('%H:%M:%S') + '| ' + msg
        if any((
                all((
                        IS_MAC,
                        kwargs.get('print', True),
                        self.uid == self.self_uid,
                        not kwargs.get('only_log', False),
                )),
                kwargs.get('force_print', False)
        )):
            print(msg)
        self.log_file.write(msg + '\n')
        if self.log_count % 100 == 0:
            self.log_file.flush()
            self.save_data()

    def _send_request(self, url, data=None, params=None, method='GET', need_sleep=True):
        method = method.upper()
        if need_sleep:
            time.sleep(1)
        else:
            time.sleep(0.1)
        if 'login' in url:
            time.sleep(2)
        try:
            if method == 'GET':
                resp = self.session.get(url, params=params, data=data)
            else:
                if isinstance(data, dict):
                    data.update({'act': 'ok'})
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

    def api_send_request(self, path, **kwargs):
        return self._send_request(BASE_URL + path, **kwargs)

    def check_login(func):
        def wrapper(self, *args, **kwargs):
            if self.session.cookies.get('uid') is None:
                self.session_init()
            check_login_resp = self._send_request(BASE_URL + 'home/my_home.html')
            if any((
                    check_login_resp.status_code != 200,
                    check_login_resp.url.find('login/login.html') != -1,
                    check_login_resp.text.find('家园社区密码：') != -1,
            )):
                self.log('需要登录')
                self.login()
            self.log('开始函数 %s', func.__name__)
            return func(self, *args, **kwargs)

        return wrapper

    def save_data(self):
        """
        保存数据
        :return: None
        """
        bot_dict[self.uid] = self
        with open('%s_uid.json' % self.uid_str, 'w') as f:
            f.write(json.dumps(
                {
                    'all_uid': list(set(self.all_uid_list)),
                    'farm_black_list': list(set(self.farm_black_list)),
                    'gather_black_list': list(set(self.gather_black_list)),
                    'garden_black_list': list(set(self.garden_black_list)),
                    'farm_done_uid': self.farm_done_uid,
                    'garden_done_uid': self.garden_done_uid,
                    'lazy_start': self.lazy_start,
                },
                indent=4,
            ))
        with open('%s_friends.json' % self.uid_str, 'w') as f:
            f.write(json.dumps(
                {
                    'friends_added': list(set(self.friends_added)),
                    'friends_black_list': list(set(self.friends_black_list)),
                },
                indent=4,
            ))
        # 保存登录态
        save_data = self.session.cookies.get_dict()
        with open('cookies.json', mode='r') as f:
            cookies = json.loads(f.read())
        cookies[str(self.uid)] = save_data
        with open('cookies.json', 'w') as f:
            f.write(json.dumps(cookies, indent=4, ensure_ascii=False))

    def session_init(self):
        try:
            with open('cookies.json', mode='r') as f:
                cookies = f.read()
                cookies = json.loads(cookies).get(str(self.uid), {})
                for k, v in cookies.items():
                    self.session.cookies.set(k, v)
            self.payment_password_verified = f'PayPass_{self.uid}' in self.session.cookies.keys()
        except json.decoder.JSONDecodeError:
            with open('cookies.json', mode='w') as f:
                f.write('{}')
        except Exception as e:
            self.log('打开 cookie 文件 异常%s', e)

    def config_init(self):
        file_path = '{}_{}.{}'
        params = [
            ('log', 'log', ''),
            ('uid', 'json', {}),
            ('friends', 'json', {}),
            ('cookies', 'json', {}),
        ]
        # 创建文件
        for file_name, file_type, default_value in params:
            if not os.path.exists(file_path.format(self.uid_str, file_name, file_type)):
                with open(file_path.format(self.uid_str, 'all_uid', file_type), mode='w') as f:
                    f.write(json.dumps(default_value))

    def once_init(self):
        # 获取今天的日期
        today = datetime.today()
        # 获取所有uid
        curr_time = int(time.time())
        with open('%s_uid.json' % self.uid_str, mode='r') as f:
            uid_dict = json.loads(f.read())
            self.all_uid_list = uid_dict.get('all_uid', [])
            self.farm_black_list = uid_dict.get('farm_black_list', [])
            self.gather_black_list = uid_dict.get('gather_black_list', [])
            self.garden_black_list = uid_dict.get('garden_black_list', [])
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
        self.q.put(self.Node(curr_time + 2, self.friends_garden, {}))
        self.q.put(self.Node(curr_time + 1, self.friends_farm, {}))

    def friends_init(self):
        with open('%s_friends.json' % self.uid_str, mode='r') as f:
            uid_dict = json.loads(f.read())
            self.friends_added = uid_dict.get('friends_added', [])
            self.friends_black_list = uid_dict.get('friends_black_list', [])
        self.all_friends_list = list(set(self.friends_added + self.friends_black_list))

    def dig_init(self):
        # self.q.put(self.Node(int(time.time()), self.dig_for_gold, {'is_gz': self.lazy_start % 2}))
        pass

    def lazy_init(self, index: int):
        # 在执行的过程中 逐步 加载uid
        old_length = len(self.all_uid_list)
        self.log('懒加载 用户长度%s', old_length)
        self.log('开始加载第%d个花园签到表 %d个农场排名表', index, index)
        res = [] if index > 10 else self.farm_friends_init(start_page=index, end_page=index)
        res.extend(self.garden_friends_init(start_index=index, end_index=index, update=True))
        self.all_uid_list.extend(res)
        self.all_uid_list = list(set(self.all_uid_list))
        if len(self.all_uid_list) > old_length:
            self.log('加载第%d个花园签到表 %d个农场排名表 加载了%d个用户', index, index, len(self.all_uid_list) - old_length)
            self.save_data()
        else:
            self.log('加载第%d个花园签到表 %d个农场排名表 结束 无新用户', index, index)

    def login(self, VerCode=None):
        login_path = 'login/login.html'
        form_data = {
            'name': self.uid,
            'pass': self.password,
        }
        if VerCode:
            time.sleep(0.1)
            form_data['VerCode'] = VerCode
        login_resp = self._send_request(BASE_URL + login_path, data=form_data, method='POST')
        if login_resp.status_code != 200:
            self.log('登录失败')
            time.sleep(0.1)
            return self.login()
        if login_resp.text.find('登录成功') != -1:
            self.log('登录成功')
            return True
        if login_resp.text.find('alt="验证码"') != -1:
            soup = bs4.BeautifulSoup(login_resp.text, 'html.parser')
            img_url = soup.select_one('body > img')['src'][1:]
            var_code_img = self._send_request(BASE_URL + img_url)
            var_code = tools.get_var_code(var_code_img.content)
            return self.login(var_code)
        if login_resp.text.find('密码错误') != -1:
            self.log('密码错误')
            return False
        return True

    @check_login
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
        friends_uid = set()
        curr_time = int(time.time())
        for i in range(start_page, end_page + 1):
            rel_path = farm_level_path.format(i)
            resp = self._send_request(BASE_URL + rel_path, need_sleep=False)
            farm_level_compile = re.compile(re_string)
            uid_list = re.findall(farm_level_compile, resp.text)
            for uid in uid_list:
                uid = int(uid)
                if any((
                    uid == self.uid,
                    uid in self.all_uid_list,
                    uid in self.all_uid_list,
                )):
                    continue
                self.q.put(self.Node(curr_time, self.steal_flower, {'friend_uid': uid}))
                self.q.put(self.Node(curr_time, self.steal_vegetables, {'friend_uid': uid}))
                friends_uid.add(uid)
        return list(friends_uid)

    @check_login
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
                if any((
                        uid == self.uid,
                        uid == self.self_uid,
                        uid in self.all_uid_list,
                )):
                    continue
                res.add(uid)
                self.q.put(self.Node(curr_time, self.steal_flower, {'friend_uid': uid}))
                self.q.put(self.Node(curr_time, self.steal_vegetables, {'friend_uid': uid}))
        return list(res)

    def xy_everyday(self, **kwargs):
        xy_path = 'home/xy_add_ok.html'
        xy_count = kwargs.get('xy_count', 1)
        data = {
            'content': '2022希望3GQQ家园社区的所有朋友幸福美满！每天开心！'
        }
        xy_resp = self._send_request(BASE_URL + xy_path, data=data, method='POST')
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

    def qd_every_day(self, **kwargs):
        qd_path = 'home/7t.html'
        qd_resp = self._send_request(BASE_URL + qd_path)
        if qd_resp.status_code != 200 or qd_resp.text.find('今天的已经领完啦') != -1:
            self.log('今天的已经签到过了')
        else:
            system_msg = tools.get_system_message(qd_resp.content)
            if len(system_msg) == 1:
                system_msg = system_msg[0]
            self.log('签到成功 %s', system_msg)
        tomorrow = int(time.time()) + 24 * 3600
        self.q.put(self.Node(tomorrow, self.qd_every_day, {}))

    def steal_vegetables(self, **kwargs):
        friend_uid = kwargs.get('friend_uid')
        self.log('开始偷菜 %s', friend_uid, print=True)
        curr_time = int(time.time())
        last_operate_time = self.farm_done_uid.get(friend_uid, 0)
        if kwargs.get('auto', True) and curr_time - last_operate_time < self.interval:
            self.q.put(self.Node(last_operate_time + self.interval, self.steal_vegetables, {'friend_uid': friend_uid}))
            self.log('农场%d操作过于频繁, %d秒后再操作', friend_uid, curr_time - last_operate_time)
            return False
        page_size = 1
        total_size = size_pre_page = 5
        page_index = 1
        steal_vegetables_path = r'game/farm/farm/%d/{}.html' % friend_uid
        # 黑名单关键词列表

        steal_black_res_list = [
            '本农场禁止摘取',
            '本农场只有好友才可以摘取！',
        ]
        curr_time = int(time.time())
        can_steal = friend_uid not in self.gather_black_list
        done = False
        next_steal_time = set()
        all_gather_res = []
        while page_index <= page_size and not done:
            real_path = steal_vegetables_path.format(page_index)
            resp = self._send_request(BASE_URL + real_path)
            if resp.url.find('farm_not') != -1:
                self.farm_black_list.append(friend_uid)
                self.q.put(self.Node(curr_time, self.save_data, {}))
                self.log('没有开通农场 加黑名单 结束 %s', friend_uid, print=True)
                return False
            content = resp.text.replace('\n', '').replace('\r', '')
            soup = bs4.BeautifulSoup(content, 'html.parser')
            vegetables = soup.select('body > div.list')[0]
            if page_size == 1:
                text = soup.select('body > div.list')[0].text
                page_size_compile = re.compile(r'\(第1/(\d*)页/共(\d*)条记录\)')
                page_size_list = re.findall(page_size_compile, text)
                # 页码数量 和 总数量
                page_size, total_size = int(page_size_list[0][0]), int(page_size_list[0][1])
                size_pre_page = int(total_size / page_size) + (total_size % page_size > 0)
            empty_count = content.count('空地')
            if empty_count == size_pre_page or (empty_count == total_size % page_size and page_index == page_size):
                page_index += 1
                continue
            vegetable_desc_compile = re.compile(r'土地\d+\((.*)/第\d季/((\d*)小时)*((\d*)分钟)*后(.*)\)')
            vegetable_ripe_compile = re.compile(r'土地\d+\((.*)\)剩\d+个,已成熟')
            for vegetable in vegetables.children:
                # 获取作物描述
                vegetable_desc = vegetable.text
                vegetable_desc_list = re.findall(vegetable_desc_compile, vegetable_desc)
                if vegetable_desc_list:
                    desc_item = vegetable_desc_list[0]
                    vegetable_name = desc_item[0]
                    need_hour = int(desc_item[2]) if desc_item[2] != '' else 0
                    need_min = int(desc_item[4]) if desc_item[4] != '' else 0
                    need_min += 1
                    next_time = curr_time + need_min * 60 + need_hour * 3600
                    next_steal_time.add(next_time)
                else:
                    vegetable_name = re.findall(vegetable_ripe_compile, vegetable_desc)
                    vegetable_name = vegetable_name[0] if vegetable_name else ''
                # 获取所有a 标签
                a_list = vegetable.select('a')
                length = len(a_list)
                if length == 0:
                    done = True
                    break
                a_text_name = a_list[0].text
                vegetable_name = vegetable_name or a_text_name
                if a_text_name in ['下页', '上页']:
                    break
                for i in range(0, length):
                    operator_name = a_list[i].text
                    if operator_name in ['收获', '除虫', '除草', '浇水', '偷菜']:
                        if operator_name == '偷菜' and not can_steal:
                            continue
                        operator_path = a_list[i].attrs['href'][1:]
                        steal_resp = self._send_request(BASE_URL + operator_path)
                        content = steal_resp.text.replace('\n', '').replace('\r', '')
                        res = tools.get_system_message(content)
                        all_gather_res.extend(res)
                        self.log('在%s 对作物%s 操作%s 结果 %s', friend_uid, vegetable_name, operator_name, res)
                        if operator_name == '偷菜' and any((content.find(k) != -1 for k in steal_black_res_list)):
                            can_steal = False
            page_index += 1
            if done:
                break
        self.farm_done_uid[friend_uid] = curr_time
        if not can_steal and friend_uid not in self.gather_black_list:
            self.gather_black_list.append(friend_uid)
        for next_time in next_steal_time:
            self.q.put(self.Node(next_time, self.steal_vegetables, {'friend_uid': friend_uid, 'auto': False}))
        if friend_uid not in self.all_friends_list and tools.check_active_user(all_gather_res):
            self.add_friends(friend_uid=friend_uid)
        self.log('偷菜结束 %s', friend_uid, print=True)
        return True

    def self_farm(self, **kwargs):
        self.log('开始打理自己的农场')
        base_path = 'game/farm/{}.html'
        operators = {
            'pick': '收获',
            'plow': '翻地',
            'plant': '种植',
            'drys': '浇水',
            'weed': '除草',
            'pest': '除虫',
            'trap': '陷阱'
        }
        for path, name in operators.items():
            rel_path = base_path.format(path)
            resp = self._send_request(BASE_URL + rel_path)
            system_message = tools.get_system_message(resp.content)
            self.log('在自己的农场操作%s 结果 %s', name, system_message)
            if path in ['plant', 'trap']:
                content = resp.text.replace('\n', '').replace('\r', '')
                soup = bs4.BeautifulSoup(content, 'html.parser')
                a_list = soup.select('body')[0].select('a')
                for a in a_list:
                    if a.text.find('选择') == -1:
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
        next_time_set = {curr_time + 5 * 60}
        for vegetable in vegetables.children:
            text = vegetable.text
            if text.find('土地') == -1:
                break
            times = re.findall(next_time_compile, text)
            if len(times):
                _, next_time_hour, next_time_min = times[0]
                next_time_hour = int(next_time_hour) if next_time_hour != '' else 0
                next_time_min = int(next_time_min)
                next_time = next_time_hour * 3600 + next_time_min * 60 + curr_time
                if next_time - curr_time > 5 * 60:
                    next_time_set.add(next_time)
        for next_time in next_time_set:
            self.q.put(self.Node(next_time, self.self_farm, {}))
        self.log('打理自己的农场结束')
        return True

    def friends_farm(self, **kwargs):
        curr_time = int(time.time())
        for uid in self.all_uid_list:
            if uid in self.farm_black_list:
                continue
            if uid in self.farm_done_uid and curr_time - self.farm_done_uid[uid] < self.interval:
                continue
            self.q.put(self.Node(curr_time, self.steal_vegetables, {'friend_uid': uid}))

    def qd_garden(self, **kwargs):
        qd_path = 'game/garden/user/hy_qd.html'
        qd_resp = self._send_request(BASE_URL + qd_path)
        if qd_resp.status_code != 200 or qd_resp.text.find('你今天领取过了，明天记得来领取独特的种子') != -1:
            self.log('花园签到 今天的已经签到过了')
        tomorrow = int(time.time()) + 24 * 3600
        self.q.put(self.Node(tomorrow, self.qd_garden, {}))

    def steal_flower(self, **kwargs):
        friend_uid = kwargs.get('friend_uid')
        self.log('开始偷花 %s', friend_uid, print=True)
        steal_flower_path = 'game/garden/garden.html'
        params = {'gid': friend_uid}
        # 收获花
        resp = self._send_request(BASE_URL + steal_flower_path, params=params)
        if resp.status_code != 200 or resp.text.find('对方没有开通花园') != -1:
            self.garden_black_list.append(friend_uid)
            self.log('没有开通花园 %s', friend_uid)
            self.q.put(self.Node(int(time.time()), self.save_data, {}))
            self.garden_black_list.append(friend_uid)
            return False
        curr_time = int(time.time())
        last_operate_time = self.garden_done_uid.get(friend_uid, 0)
        if kwargs.get('auto', True) and curr_time - last_operate_time < self.interval:
            self.q.put(self.Node(last_operate_time + self.interval, self.steal_vegetables, {'friend_uid': friend_uid}))
            self.log('花园%d操作过于频繁, %d秒后再操作', friend_uid, curr_time - last_operate_time)
            return False
        # 获取下次来操作的时间
        content = resp.text.replace('\n', '').replace('\r', '')
        soup = bs4.BeautifulSoup(content, 'html.parser')
        all_text = soup.select('body')[0].text
        next_time_compile = re.compile(r'(\d*)分钟后')
        next_time_list = re.findall(next_time_compile, all_text)
        curr_time = int(time.time())
        next_steal_times = set()
        for next_time_min in next_time_list:
            m = int(next_time_min)
            next_time = curr_time + m * 60
            next_steal_times.add(next_time)
        for next_time in next_steal_times:
            self.log('%s 在%s 分钟后操作', friend_uid, (next_time - curr_time) // 60)
            self.q.put(self.Node(next_time, self.steal_flower, {'friend_uid': friend_uid, 'auto': False}))
        # 操作列表 浇水.锄草.捉虫.偷菜
        operators = {
            'watera': '浇水',
            'weeda': '锄草',
            'pesta': '捉虫',
            'gathera': '偷花'
        }
        operator_path = 'game/garden/{}/{}.html'
        all_gather_res = []
        for operator, name in operators.items():
            real_path = operator_path.format(operator, friend_uid)
            operator_resp = self._send_request(BASE_URL + real_path)
            operator_msg = tools.get_system_message(operator_resp.content)
            if operator == 'gathera' and len(operator_msg) == 0:
                content = operator_resp.text.replace('\n', '').replace('\r', '')
                soup = bs4.BeautifulSoup(content, 'html.parser')
                gathera_res = soup.select('body > div.list')[0]
                for gather_res in gathera_res.children:
                    if gather_res.text != '':
                        operator_msg.append(gather_res.text)
            all_gather_res.extend(operator_msg)
            self.log('%d 花园 操作%s 结果%s', friend_uid, name, operator_msg)
        self.garden_done_uid[friend_uid] = curr_time
        if friend_uid not in self.all_friends_list and tools.check_active_user(all_gather_res):
            self.add_friends(friend_uid=friend_uid)
        self.log('偷花结束 %s', friend_uid, print=True)
        return True

    def friends_garden(self, **kwargs):
        curr_time = int(time.time())
        for uid in self.all_uid_list:
            if uid in self.garden_black_list:
                continue
            if uid in self.garden_done_uid and curr_time - self.garden_done_uid[uid] < self.interval:
                continue
            self.q.put(self.Node(curr_time, self.steal_flower, {'friend_uid': uid}))

    def self_garden(self, **kwargs):
        self.log('开始打理自己的花园')
        operators = {
            '收获': 'gathera',
            '播种': 'sowing_list',
            '浇水': 'watera',
            '锄草': 'weeda',
            '捉虫': 'pesta',
        }
        operator_path = 'game/garden/user/{}.html'
        curr_time = int(time.time())
        for name, path in operators.items():
            operator_resp = self._send_request(BASE_URL + operator_path.format(path))
            if path == 'sowing_list':
                content = operator_resp.text.replace('\n', '').replace('\r', '')
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
                    sowing_item_msg = tools.get_system_message(sowing_item_resp.content)
                    if not sowing_item_msg:
                        break
                    self.log('自己的花园 播种%s 数量%d 结果%s', item_name, item_count, sowing_item_msg)
            else:
                operator_msg = tools.get_system_message(operator_resp.content)
                self.log('自己的花园 操作%s 结果%s', name, operator_msg)

        self.q.put(self.Node(curr_time + 5 * 60, self.self_garden, {}))
        self.log('打理自己的花园结束')
        return True

    def get_money_status(self, status_type=False):
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
            my_gb_compile = re.compile(r'元宝余额:(-*\d+)')
            a = int(my_gb_compile.search(text).group(1))
            if a <= 30000:
                y = 8
                for ky, vl in status_type_map.items():
                    if a >= ky:
                        y = vl
                return a, y
        else:
            my_gb_compile = re.compile(r'GB余额:(-*\d+)')
            a = int(my_gb_compile.search(text).group(1))
        z = a // 30
        y = z - 1
        for bit_pos in [1, 2, 4, 8, 16]:
            y |= (y >> bit_pos)
        y += 1
        y = y if abs((y >> 1) - z) > abs(y - z) else y >> 1
        return a, y

    def verify_payment_password(self):
        v_pass_path = 'home/money/vpass.html'
        save_money_path = 'home/money/trade_add.html'
        v_pass_params = {
            'srcurl': '/' + save_money_path,
        }
        form_data = {
            'vpass': self.v_pass,
        }
        v_pass_resp = self._send_request(BASE_URL + v_pass_path, params=v_pass_params, data=form_data, method='POST')
        if v_pass_resp.text.find('校验成功') == -1:
            self.log('验证支付密码失败')
            return False
        self.payment_password_verified = True
        self.save_data()
        return True

    @check_login
    def pay_money(self, save_balance, save_type=0, t_uid=35806354, detail='', second=False):
        save_balance = int(save_balance)
        # 1 验证支付密码
        if not self.payment_password_verified:
            self.verify_payment_password()
        save_money_path = 'home/money/trade_add.html'
        # 2 提交 支付
        form_data = {
            'type': 1,                    # 贸易类型 1 即时 2 担保
            'money': save_type,           # 转账货币类型 0 GB 1 元宝
            'amount': save_balance,       # 转账金额
            'detail': str(detail),        # 转账说明
            'tuid': t_uid,                # 转账目标
            'tmoney': '',                 # 索要货币类型
            'tamount': '',                # 索要货币数量
        }
        save_money_resp = self._send_request(BASE_URL + save_money_path, data=form_data, method='POST')
        # 确认支付
        save_money_content = save_money_resp.text.replace('\n', '').replace('\r', '').replace(' ', '')
        if save_money_content.find('确认提交') == -1:
            if not second and save_money_content.find('请输入您的支付密码进行验证') != -1:
                self.payment_password_verified = False
                self.verify_payment_password()
                return self.pay_money(save_balance, save_type, t_uid,detail, second=True)
            self.log('提交交易失败')
            return False
        t_id = int(re.search(r'type="hidden"name="tid"value="(\d+)"/>', save_money_content).group(1))
        form_data = {
            'tid': t_id,
        }
        # 3 提交确认
        save_money_resp = self._send_request(BASE_URL + save_money_path, data=form_data, method='POST')
        if save_money_resp.text.find('发布成功！') == -1:
            self.log('确认交易失败')
            return False
        self.log('转账成功 %s', save_balance, say=True)
        return True

    # 激情挖宝
    @check_login
    def dig_for_gold(self, **kwargs):
        def get_box_id():
            return random.randint(1, 16)

        is_gz = kwargs.get('is_gz', False)
        yb_balance, yb_interval = self.get_money_status(True)
        gb_balance, gb_interval = self.get_money_status(False)
        balance, interval = (yb_balance, yb_interval) if is_gz else (gb_balance, gb_interval)
        if balance <= 1000 or balance >= 1.8e9:
            self.log('余额边界 %s', balance, say=True)
            return balance
        self.log('开始 数量%d 押注上限 %d', balance, interval, only_log=True)
        play_path = '/game/diggingtreasure/play.aspx'
        if is_gz:
            play_path = play_path.replace('play', 'play2')
        box_number = kwargs.get('box_number') or get_box_id()
        params = {'num1': box_number}
        all_failed_count = 0
        fail_count = 0
        success_count = 0
        first_curr_number = 1
        over_exp = 2
        curr_number = first_curr_number
        new_money = 0
        interval_count = 0
        curr_count = 0
        max_dig = kwargs.get('max_dig', 100)
        fail_count_list = []
        max_curr_count = 1 if balance >= 2e4 else 2 if balance >= 1e4 else 3
        for i in range(1, max_dig + 1):
            box_number = 8
            if curr_count >= max_curr_count:
                curr_number = min(int(curr_number * over_exp), interval)
                curr_count = 0
            curr_count += 1
            if curr_number == interval:
                interval_count += 1
            else:
                interval_count = 0
            params['num'] = curr_number
            params['num1'] = box_number
            new_money -= curr_number
            resp = self._send_request(BASE_URL + play_path, params=params)
            content = resp.text.replace('\n', '').replace('\r', '')
            if content.find('眼前一片金光四射') != -1:
                fail_count_list.append(fail_count)
                new_money += curr_number * 6
                all_failed_count += fail_count
                success_count += 1
                self.log('激情挖宝 成功 成本%s 盈利 %s', curr_number, new_money, only_log=True)
                self.log('平均挖宝次数 %.2f 成功率%.2f', i / success_count, success_count / i, only_log=True)
                # box_number = get_box_id()
                fail_count = 0
                curr_number = first_curr_number
                curr_count = 0
                if max_dig - i <= 10 or (max_dig - i <= 20 and max(fail_count_list) < 10):
                    self.log('剩余次数不足%d次 撤了', max(fail_count_list), only_log=True)
                    break
            else:
                self.log('激情挖宝 失败 成本%s', curr_number, only_log=True)
                fail_count += 1
        if fail_count:
            all_failed_count += fail_count
            fail_count_list.append(fail_count)
        got_type = '元宝' if is_gz else '金币'
        is_add = '挣了' if new_money >= 0 else '亏了'
        new_balance, interval = self.get_money_status(is_gz)
        self.log(
            '%s%s%d余额%d',
            got_type,
            is_add,
            abs(new_money),
            new_balance,
            say=abs(new_money) >= 5e7,
            only_log=True
        )
        self.log(
            '成功%d次 失败%d次 结算%d 失败列表%s',
            success_count,
            all_failed_count,
            new_money,
            fail_count_list,
            only_log=True,
        )
        return new_balance

    # 抢车位
    @check_login
    def rob_car(self, **kwargs):
        my_car_path = 'game/car/my_garage.html'
        rob_car_path = 'game/car/stop_cara.html'
        favor_car_path = 'game/car/favor_cara.html'
        while True:
            self.log('开始抢车位')
            my_car_resp = self._send_request(BASE_URL + my_car_path)
            content = my_car_resp.text.replace('\n', '').replace('\r', '')
            # 提取停车时间
            stop_times = re.findall(r'停车时间:(\d*)分钟/(\d*)小时', content)
            next_start_time = 20 * 60 * 60
            if len(stop_times) or content.find('流动中') != -1:
                if len(stop_times):
                    stop_time_min, stop_time_hour = int(stop_times[0][0]), int(stop_times[0][1])
                else:
                    stop_time_min, stop_time_hour = 24, 24
                self.log(
                    '停车时间%d分钟/%d小时, 是否流动中%s',
                    stop_time_min, stop_time_hour, stop_time_min == 24 and stop_time_hour == 24,
                    print=True,
                )
                if stop_time_min >= 20 * 60 or stop_time_hour >= 20:
                    # 一键 停车 收车地址
                    self.log('一键 收车 停车')
                    # 收车
                    self._send_request(BASE_URL + favor_car_path)
                    # 一键停车
                    self._send_request(BASE_URL + rob_car_path)
                else:
                    next_start_time = next_start_time - stop_time_min * 60
            else:
                self.log('意外情况')
                next_start_time = 60 * 60
            self.log('等待%d秒', next_start_time)
            time.sleep(next_start_time)

    # 加好友
    @check_login
    def add_friends(self, **kwargs):
        friend_uid = kwargs.get('friend_uid')
        self.log('开始加好友 %s', friend_uid)
        # 社区好友
        add_friend_path = f'/home/friend_add/{friend_uid}.html'
        form_data = {
            'name': '',
            'label': '35806119.02',
            'remark': '白雪公主',
        }
        add_friend_resp = self._send_request(BASE_URL + add_friend_path, data=form_data, method='POST')
        text = add_friend_resp.text.replace('\n', '').replace('\r', '')
        if text.find('添加成功！') != -1:
            self.log('添加好友 %s 成功', friend_uid)
            self.friends_added.append(friend_uid)
            add_res = True
        elif text.find('请不要重复添加！') != -1:
            self.friends_added.append(friend_uid)
            add_res = True
        else:
            add_res = False
            self.friends_black_list.append(friend_uid)
            self.log('添加好友失败')
        self.all_friends_list.append(friend_uid)
        # 添加农场邻居
        add_neighbor_path = 'game/farm/neighbor_add.html'
        form_data = {
            'fid': friend_uid
        }
        self._send_request(BASE_URL + add_neighbor_path, data=form_data, method='POST')
        return add_res

    @check_login
    def run(self):
        task_index = 0
        if self.q.empty():
            # self.config_init()
            self.session_init()
            self.once_init()
            self.friends_init()
            self.dig_init()
        while not self.q.empty():
            task = self.q.get()
            curr_time = int(time.time())
            self.log('已执行%s, 队列长度 %s', task_index, self.q.qsize(), force_print=True)
            if task_index % 20 == 0:
                # self.dig_init()
                self.lazy_init(index=self.lazy_start)
                self.lazy_start = (self.lazy_start + 1) % 200 + 1
            if curr_time >= task.time:
                self.log('开始任务 %s, %s', task.name, task.kwargs)
                task.func(**task.kwargs)
                task_index += 1
            else:
                self.q.put(task)
                wait_time = task.time - curr_time
                self.log('sleep %d', wait_time)
                while wait_time > 10:
                    self.lazy_init(index=self.lazy_start)
                    self.dig_for_gold(is_gz=self.lazy_start % 2 != 0)
                    self.lazy_start += 1
                    time.sleep(5)
                    wait_time = task.time - int(time.time())
                wait_time = max(0.1, wait_time)
                time.sleep(wait_time)


def get_bot(uid, **kwargs) -> Bot:
    res = bot_dict.get(uid, None)
    if res is None:
        res = Bot(uid=uid, **kwargs)
        bot_dict[uid] = res
    return res


def run(p_uid):
    time.sleep(random.randint(0, 10))
    b = get_bot(p_uid)
    play2 = 1
    first_yb, _ = b.get_money_status(status_type=True)
    first_gb, _ = b.get_money_status(status_type=False)
    pre_yb, pre_gb = first_yb, first_gb
    yb_check, gb_check = 0 <= first_yb <= 1e9, 0 <= first_gb <= 1e9
    p_uid_str = str(p_uid)[-3:]
    friends_map = {
        35806119: 35806354,
        35806354: 35806119,
    }
    while True:
        try:
            while yb_check or gb_check or b.uid != b.self_uid:
                got_yb = play2 % 2 == 0
                if yb_check != gb_check:
                    got_yb = yb_check
                any_balance = b.dig_for_gold(is_gz=got_yb, max_dig=100)
                if any_balance >= int(1.5e9):
                    pay(
                        receive_money_uid=friends_map[b.uid],
                        pay_uid=b.uid,
                        pay_number=int(1e8),
                        pay_type=int(got_yb),
                        auto=False,
                    )
                if got_yb:
                    got_name = '元宝'
                    got_number = any_balance - first_yb
                    got_res = '挣了' if got_number > 0 else '亏了'
                    b.log('%s %s%s%s', p_uid_str, got_name, got_res, abs(got_number), say=True)
                    got_number = any_balance - pre_yb
                    yb_check = any_balance <= 1e9
                else:
                    got_name = '金币'
                    got_number = any_balance - first_gb
                    got_res = '挣了' if got_number > 0 else '亏了'
                    b.log('%s %s%s%s', p_uid_str, got_name, got_res, abs(got_number), say=True)
                    got_number = any_balance - pre_gb
                    gb_check = any_balance <= 1e9
                got_res = '挣了' if got_number > 0 else '亏了'
                b.log(
                    '%s %s%s%d 余额%d',
                    p_uid_str, got_name, got_res, abs(got_number), any_balance,
                    force_print=True,
                )
                pre_yb = any_balance if got_yb else pre_yb
                pre_gb = any_balance if not got_yb else pre_gb
                play2 += 1
            b.run()
        except Exception as e:
            info = traceback.format_exc()
            b.log('异常是%s 堆栈是 %s', e, info, say=True, force_print=True)
            b.log('重启', say=True, force_print=True)


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
    if receive_money_uid == pay_uid:
        print('收款人和付款人不能相同')
        return
    b = get_bot(uid=pay_uid)
    pay_name = '元宝' if pay_type else '金币'
    if receive_money_uid in MY_UID_LIST:
        receive_b = get_bot(uid=receive_money_uid)
        balance, _ = receive_b.get_money_status(pay_type)
        if balance >= 1.8e9:
            print('收款人余额已达上限')
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
        need_vpass=False,
):
    if data is None:
        data = {}
    if params is None:
        params = {}
    b = get_bot(uid=uid)
    if need_vpass:
        b.verify_payment_password()
    send_count = 0
    while send_count < request_count:
        send_count += 1
        b.api_send_request(path, data=data, params=params, method=method)
        b.log('第%d次请求完成', send_count, force_print=True)


if __name__ == '__main__':
    if len(sys.argv) > 1:
        p_count = int(sys.argv[1])
    if p_count == -1:
        pay(auto=True)
        sys.exit(0)
    if p_count == 0:
        user_id = int(sys.argv[2]) if len(sys.argv) > 2 else 35806119
        get_bot(uid=user_id).rob_car()
        sys.exit(0)
    if p_count == 1:
        user_id = int(sys.argv[2]) if len(sys.argv) > 2 else 35806119
        run(p_uid=user_id)
    p = multiprocessing.Pool(processes=2)
    all_user = [
        35806119,
        35806354,
    ]
    for user_id in all_user:
        p.apply_async(run, args=(user_id,))
    p.close()
    p.join()
