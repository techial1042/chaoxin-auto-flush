import os

import re
import random
import json
import requests
import pickle
import hashlib
import base64
import time


class ChaoXing:
    def __init__(self, username: str, password: str, chapter_id: str, clazz_id: str, course_id: str):
        self.chapter_id = chapter_id
        self.clazz_id = clazz_id
        self.course_id = course_id

        self.__init_session()
        self.__load_session(username, password)

        self.__get_my_arg()

    def __exit__(self, exc_type, exc_value, traceback):
        self.dump_session()

    def __init_session(self):
        """
        session 初始化，session 共享
        """
        headers = {
            'Connection': 'keep-alive',
            'DNT': '1',
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 11_0_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.67 Safari/537.36',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'Origin': 'http://mooc1-1.chaoxing.com',
            'Accept-Language': 'en',
        }

        self.session = requests.Session()
        self.session.headers = headers

    def __load_session(self, username, password):
        """
        从本地磁盘加载 session，若文件不在，则 HTTP 登录
        """
        if os.path.exists("cookie.bin"):
            with open('cookie.bin', 'rb') as f:
                self.session.cookies.update(pickle.load(f))
            print("Session from local disk.")
        else:
            self.__login(username, password)
            print("Session from login request.")

    def dump_session(self):
        """
        将 session 保存到本地磁盘
        """
        with open('cookie.bin', 'wb') as f:
            pickle.dump(self.session.cookies, f)

    def __login(self, username, password):
        """
        超星登录接口
        """
        payload = {
            'fid': '2182',
            'uname': username,
            'password': base64.b64encode(password.encode('ascii')).decode('ascii'),
            'refer': 'https://mooc1-1.chaoxing.com',
            't': 'true'
        }
        login = self.session.post(url='https://passport2.chaoxing.com/fanyalogin',
                                  data=payload)
        print('Http code: {}, text: {}'.format(login.status_code, login.text))

    def __get_my_arg(self):
        """
        获得课程信息
        """
        url = 'https://mooc1-1.chaoxing.com/knowledge/cards'
        requests_params = {
            'clazzid': self.clazz_id,
            'courseid': self.course_id,
            'knowledgeid': self.chapter_id
        }
        result = self.session.get(url, params=requests_params).text
        return self.__arg_handler(result)

    def __arg_handler(self, text):
        """
        从 HTML 中获得参数
        """
        arg = re.findall('mArg = (.*);', text, re.MULTILINE)[1]
        print('args = \n{}'.format(arg))
        self.arg_json = json.loads(arg)
        self.user_id = self.arg_json['defaults']['userid']

    def play(self):
        cpi = self.arg_json['defaults']['cpi']
        attachments = self.arg_json['attachments']
        for attachment in attachments:
            object_id = attachment['property']['objectid']

            status_json = self.__get_play_status(object_id)
            params = self.__get_params(attachment['jobid'], attachment['property']['objectid'], 0,
                                       status_json['duration'], None, None, attachment['otherInfo'], None, 0)
            audio_play = self.session.get(
                url='https://mooc1-1.chaoxing.com/multimedia/log/a/{}/{}'.format(cpi, status_json['dtoken']),
                params=params)

            print('boom, object_id: {}, params: {}'.format(object_id, params))
            print('boom, result {}'.format(audio_play.text))
            status_json = self.__get_play_status(object_id)
            params = self.__get_params(attachment['jobid'], attachment['property']['objectid'], status_json['duration'],
                                       status_json['duration'], None, None, attachment['otherInfo'], None, 4)
            audio_play = self.session.get(
                url='https://mooc1-1.chaoxing.com/multimedia/log/a/{}/{}'.format(cpi, status_json['dtoken']),
                params=params)

            print('boom, object_id: {}, params: {}'.format(object_id, params))
            print('boom, result {}'.format(audio_play.text))

            time.sleep(random.randint(3, 10))

    def __get_play_status(self, object_id):
        """
        获得视频 / 音频基本信息
        """
        status = self.session.get('https://mooc1-1.chaoxing.com/ananas/status/{}'.format(object_id),
                                  params={'_dc': int(time.time() * 1000)})
        print('student study url = {}'.format(status.url))
        return status.json()

    def __get_params(self, job_id: str, object_id: str, playing_time: int, duration: int, start_time, end_time,
                     other_info, rt, is_drag):
        """
        请求参数构建
        """
        clip_time = ChaoXing.__get_clip_time(duration, start_time, end_time)
        view = 'pc'
        enc = self.__get_enc(job_id, object_id, playing_time, duration, start_time, end_time)
        dtype = 'Audio'
        t = int(time.time() * 1000)

        return {
            'clazzId': self.clazz_id,
            'playingTime': playing_time,
            'duration': duration,
            'clipTime': clip_time,
            'objectId': object_id,
            'otherInfo': other_info,
            'jobid': job_id,
            'userid': self.user_id,
            'isdrag': is_drag,
            'view': view,
            'enc': enc,
            'rt': rt,
            'dtype': dtype,
            '_t': t
        }

    def __get_enc(self, job_id: str, object_id: str, playing_time: int, duration: int, start_time, end_time):
        """
        enc 参数加密
        """
        if job_id is None:
            job_id = ""

        clip_time = ChaoXing.__get_clip_time(duration, start_time, end_time)

        enc_str = '[{0}][{1}][{2}][{3}][{4}][{5}][{6}][{7}]'.format(
            self.clazz_id,
            self.user_id,
            job_id,
            object_id,
            playing_time * 1000,
            "d_yHJ!$pdA~5",
            duration * 1000,
            clip_time)
        return hashlib.md5(enc_str.encode()).hexdigest()

    @staticmethod
    def __get_clip_time(duration: int, start_time, end_time):
        """
        clip_time 参数构建
        """
        if start_time is None:
            start_time = "0"

        tmp = end_time
        if end_time is None:
            tmp = duration

        return '{}_{}'.format(start_time, tmp)
